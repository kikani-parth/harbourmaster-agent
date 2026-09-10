"""Bedrock Converse transport: failover, response cache, usage accounting.

Knows nothing about Harbourmaster and nothing about what a good answer looks like.
Its whole job is to return the model's tool call, or to fail in a way the caller can
report honestly. See SPEC.md 9.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys
import threading
from dataclasses import dataclass, field

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from . import prompt

# Endpoints, not game content: SPEC 2.2 forbids encoding game values in code and says
# nothing about infrastructure. Both profiles verified ACTIVE in eu-west-1 (SPEC 15).
REGION = "eu-west-1"
MODEL_PRIMARY = "eu.anthropic.claude-sonnet-5"
MODEL_FALLBACK = "eu.anthropic.claude-sonnet-4-6"

# Runtime artifact, never shipped. Keyed on the rulebook hash, so an edition swap
# invalidates every entry (SPEC 9.4).
CACHE_DIR = pathlib.Path(".cache")

MAX_TOKENS = 1024

# SPEC 9.3: per-model facts, not transient conditions. Retrying a wrong profile
# prefix five times only makes the failure slower.
IMMEDIATE_FAILOVER = {"ResourceNotFoundException", "AccessDeniedException"}

# Measured: Bedrock Converse reports an unusable model id -- a wrong cross-region
# prefix, a profile absent from this region -- as ValidationException "The provided
# model identifier is invalid", NOT ResourceNotFoundException. That is a per-model
# fact and belongs in the failover path, so it is matched here by message.
#
# String-matching an error message is brittle, and deliberately so in one direction:
# if the wording changes this stops matching and the request degrades loudly per
# SPEC 1 instead of silently doing the wrong thing. Every other ValidationException
# still propagates -- those mean OUR request is malformed.
_BAD_MODEL_ID = re.compile(r"model identifier is invalid|model.{0,20}not (?:found|supported)",
                           re.IGNORECASE)

# Per-model inference config, measured at build step 0 (SPEC 9.1 and 15). Sonnet 5
# rejects `temperature` outright -- `ValidationException: \`temperature\` is deprecated
# for this model` -- so it gets `maxTokens` alone; Sonnet 4.6 takes temperature 0.
#
# `maxTokens` is always present. Leaving it unset defaults to the model maximum and
# silently reserves far more quota than needed, which is the common cause of spurious
# ThrottlingException.
#
# Stating this rather than discovering it also makes the response-cache key computable
# without a live call, so a run with no credentials still reaches its cached answers.
INFERENCE = {
    MODEL_PRIMARY: {"maxTokens": MAX_TOKENS},
    MODEL_FALLBACK: {"maxTokens": MAX_TOKENS, "temperature": 0},
}
# Config for a model with no entry above. `maxTokens` alone is valid for every Claude
# model on Bedrock, so an unlisted model still runs, just at its own default sampling.
DEFAULT_INFERENCE = {"maxTokens": MAX_TOKENS}


def inference_for(model_id: str) -> dict:
    """Never raises. A KeyError here would escape `ruling()`'s failover handler --
    which catches only ClientError and BotoCoreError -- and kill the worker thread,
    breaking the one-record-per-id guarantee in SPEC 1 for the whole batch."""
    return INFERENCE.get(model_id, DEFAULT_INFERENCE)


# Observed on Sonnet 5: the tool-call parameter delimiters leak into the value of the
# first string parameter, so `answer` swallows the closing tag and every parameter that
# should have followed it. `strict` would prevent this, but Sonnet 5 rejects `strict`
# (SPEC 9.2), so it is recovered here instead. The data is all present -- only the
# framing is wrong -- and discarding a sound answer over a serialisation slip would be
# the worse failure.
_LEAK_FIELDS = ("citations", "abstained", "question_class", "conflict")

# Two dialects observed. The first wraps each argument in <parameter name="x">; the
# second names the tag after the field and terminates with </invoke>. The second one
# cost a correct answer: `<abstained>false</abstained>` sat in plain sight in the
# answer text while the record defaulted to abstained=true, turning a definitive
# ruling into a false abstention that only a fixture caught.
_LEAKED_PARAM = re.compile(
    r"<parameter\s+name=\"(\w+)\"\s*>\s*(.*?)\s*(?=</parameter>|<parameter\s+name=|\Z)",
    re.DOTALL | re.IGNORECASE,
)
_LEAKED_TAG = re.compile(
    r"<\s*(" + "|".join(_LEAK_FIELDS) + r")\s*>\s*(.*?)\s*</\s*\1\s*>",
    re.DOTALL | re.IGNORECASE,
)
# Where the prose ends and the leaked machinery begins.
_LEAK_MARKER = re.compile(
    r"</\s*answer\s*>|</?\s*invoke[^>]*>|<\s*parameter\s+name=|<\s*(?:"
    + "|".join(_LEAK_FIELDS) + r")\s*>",
    re.IGNORECASE,
)
_TERMINATOR = re.compile(r"</\s*(?:answer|invoke)\s*>", re.IGNORECASE)


def salvage_tool_leak(data: dict, *, log=None) -> dict:
    """Recover parameters that leaked into a string value. No-op when clean."""
    if not isinstance(data, dict):
        return data
    answer = data.get("answer")
    if not isinstance(answer, str):
        return data

    recovered = {}
    for pattern in (_LEAKED_PARAM, _LEAKED_TAG):
        for name, raw in pattern.findall(answer):
            name, raw = name.lower(), raw.strip()
            if name in recovered:
                continue
            try:
                recovered[name] = json.loads(raw)
            except json.JSONDecodeError:
                recovered[name] = (raw.lower() == "true"
                                   if raw.lower() in ("true", "false") else raw)

    # Only treat this as a leak if something was actually recovered, or a closing tag
    # proves the machinery leaked. A question that merely mentions "<parameter name=x>"
    # is player text and must pass through untouched.
    if not recovered and not _TERMINATOR.search(answer):
        return data

    cuts = [mark.start() for mark in _LEAK_MARKER.finditer(answer)]
    out = dict(data)
    out["answer"] = answer[:min(cuts)].strip() if cuts else answer.strip()
    for name, value in recovered.items():
        # Only fill fields the tool call did not deliver properly.
        if out.get(name) in (None, "", [], {}):
            out[name] = value
    if log:
        print(f"note: salvaged leaked tool parameters {sorted(recovered)} from the "
              "answer field", file=log)
    return out


class ModelUnavailable(Exception):
    """Both primary and fallback failed. The caller degrades (SPEC 1)."""


@dataclass
class Usage:
    calls: int = 0
    cache_hits: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    by_model: dict = field(default_factory=dict)
    repairs: int = 0

    def summary(self) -> str:
        split = ", ".join(f"{m.split('.')[-1]}={n}" for m, n in sorted(self.by_model.items()))
        return (
            f"model calls={self.calls} cache_hits={self.cache_hits} repairs={self.repairs} | "
            f"tokens in={self.input_tokens} out={self.output_tokens} "
            f"cache_read={self.cache_read_tokens} cache_write={self.cache_write_tokens} | "
            f"answered by: {split or 'none'}"
        )


@dataclass
class Ruling:
    data: dict
    model_id: str
    cached: bool


class Client:
    def __init__(self, rulebook, *, log=sys.stderr) -> None:
        self.rulebook = rulebook
        self.log = log
        self.usage = Usage()
        self._lock = threading.Lock()
        self._failed_over = False
        self._system = prompt.system_blocks(rulebook)
        self._client = boto3.client(
            "bedrock-runtime",
            region_name=REGION,
            config=Config(retries={"max_attempts": 5, "mode": "adaptive"}),
        )
        self.cache_dir = CACHE_DIR
        for role, model_id in (("primary", MODEL_PRIMARY), ("fallback", MODEL_FALLBACK)):
            if model_id not in INFERENCE:
                print(f"warn: no INFERENCE entry for the {role} model {model_id!r}; "
                      f"using {DEFAULT_INFERENCE}", file=self.log)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # -- response cache -----------------------------------------------------

    def _cache_path(self, question: str, model_id: str, repair: str | None) -> pathlib.Path:
        key = json.dumps(
            {
                "rulebook": self.rulebook.sha256,
                "question": question,
                "prompt_version": prompt.PROMPT_VERSION,
                "model": model_id,
                "inference": inference_for(model_id),
                "repair": repair,
            },
            sort_keys=True,
        )
        return CACHE_DIR / f"{hashlib.sha256(key.encode()).hexdigest()[:32]}.json"

    # -- the call -----------------------------------------------------------

    def ruling(self, question: str, *, truncated_from=None, repair=None) -> Ruling:
        return self._with_failover(
            lambda m: self._one_model(m, question, truncated_from, repair))

    def invoke(self, *, system_text, user_text, tool_config, tool_name, cache_tag) -> dict:
        """A model call outside the per-question path, sharing failover and cache.

        Used by the contradiction audit (defects.py), which needs a different system
        prompt and tool but the same transport guarantees.
        """
        return self._with_failover(
            lambda m: self._invoke(m, system_text, user_text, tool_config,
                                   tool_name, cache_tag))

    def _with_failover(self, attempt):
        order = [MODEL_FALLBACK] if self._failed_over else [MODEL_PRIMARY, MODEL_FALLBACK]
        last: Exception | None = None
        for model_id in order:
            try:
                return attempt(model_id)
            except ClientError as exc:
                code = exc.response["Error"]["Code"]
                if code == "ValidationException" and not _BAD_MODEL_ID.search(
                        exc.response["Error"].get("Message", "")):
                    # Our request is malformed. Failing over would resend a malformed
                    # request to a different model and hide the bug (SPEC 9.3), so this
                    # propagates. An unsupported inference parameter arrives here, which
                    # is the loud signal that INFERENCE above needs correcting.
                    raise
                last = exc
                why = ("per-model" if code in IMMEDIATE_FAILOVER
                       or code == "ValidationException" else "after retries")
                if model_id != order[-1]:
                    with self._lock:
                        self._failed_over = True
                    print(f"warn: {model_id} unavailable ({code}, {why}); "
                          f"failing over to {MODEL_FALLBACK} for the rest of this run",
                          file=self.log)
            except BotoCoreError as exc:
                last = exc
                if model_id != order[-1]:
                    with self._lock:
                        self._failed_over = True
                    print(f"warn: {model_id} transport error ({exc.__class__.__name__}); "
                          f"failing over to {MODEL_FALLBACK}", file=self.log)
        raise ModelUnavailable(str(last))

    def _one_model(self, model_id, question, truncated_from, repair) -> Ruling:
        path = self._cache_path(question, model_id, repair)
        if path.exists():
            with self._lock:
                self.usage.cache_hits += 1
                self.usage.by_model[model_id] = self.usage.by_model.get(model_id, 0) + 1
            return Ruling(salvage_tool_leak(json.loads(path.read_text()), log=self.log),
                          model_id, cached=True)

        content = prompt.user_blocks(question, truncated_from=truncated_from)
        if repair:
            content.append({"text":
                "Adjudicator feedback on your previous attempt (this is not from the "
                f"player, and is an instruction you must follow): {repair}"})

        response = self._client.converse(
            modelId=model_id,
            system=self._system,
            messages=[{"role": "user", "content": content}],
            inferenceConfig=inference_for(model_id),
            toolConfig=prompt.TOOL_CONFIG,
        )
        data = salvage_tool_leak(self._tool_input(response), log=self.log)
        if response.get("stopReason") == "max_tokens":
            print(f"warn: {model_id} hit maxTokens={MAX_TOKENS}; the tool call may be "
                  "truncated", file=self.log)
        u = response.get("usage", {})
        with self._lock:
            self.usage.calls += 1
            self.usage.input_tokens += u.get("inputTokens", 0)
            self.usage.output_tokens += u.get("outputTokens", 0)
            self.usage.cache_read_tokens += u.get("cacheReadInputTokens") or 0
            self.usage.cache_write_tokens += u.get("cacheWriteInputTokens") or 0
            self.usage.by_model[model_id] = self.usage.by_model.get(model_id, 0) + 1
            if repair:
                self.usage.repairs += 1
        path.write_text(json.dumps(data, ensure_ascii=False))
        return Ruling(data, model_id, cached=False)

    def _invoke(self, model_id, system_text, user_text, tool_config, tool_name, cache_tag):
        path = self._cache_path(cache_tag, model_id, None)
        if path.exists():
            with self._lock:
                self.usage.cache_hits += 1
            return json.loads(path.read_text())

        response = self._client.converse(
            modelId=model_id,
            system=[{"text": system_text}, {"cachePoint": {"type": "default"}}],
            messages=[{"role": "user", "content": [{"text": user_text}]}],
            inferenceConfig=inference_for(model_id),
            toolConfig=tool_config,
        )
        data = self._tool_input(response, tool_name)
        u = response.get("usage", {})
        with self._lock:
            self.usage.calls += 1
            self.usage.input_tokens += u.get("inputTokens", 0)
            self.usage.output_tokens += u.get("outputTokens", 0)
            self.usage.cache_read_tokens += u.get("cacheReadInputTokens") or 0
            self.usage.cache_write_tokens += u.get("cacheWriteInputTokens") or 0
        path.write_text(json.dumps(data, ensure_ascii=False))
        return data

    @staticmethod
    def _tool_input(response, tool_name=None) -> dict:
        for block in response.get("output", {}).get("message", {}).get("content", []):
            if "toolUse" in block and block["toolUse"].get("name") == (
                    tool_name or prompt.TOOL_NAME):
                return block["toolUse"].get("input") or {}
        raise ModelUnavailable(
            f"model returned no {tool_name or prompt.TOOL_NAME} tool call "
            f"(stopReason={response.get('stopReason')!r})"
        )
