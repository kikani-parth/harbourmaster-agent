### 1. Where I overruled the agent on substance

L698 → L702/L727, then L841.

Sonnet 5 rejects the deprecated `temperature` parameter, so it had these parameter-discovery functions which the agent discovered at runtime and then remembered it. At L698 I told it to remove the whole parameter-discovery setup and hardcode the config per model instead. Sonnet 4.6 gets `maxTokens` and `temperature`, Sonnet 5 gets `maxTokens` only. The reasoning was that this just added more complexity to the code and the cache key needed live credentials to compute.

It agreed ("This is a better fix than the one I made earlier" — L702) and deleted `_note_unsupported`, `_load_unsupported`, `_save_unsupported`, `PARAMS_FILE`, `BASE_INFERENCE` and `_DEPRECATED_PARAM` (L727).

But that simplification introduced the `INFERENCE[model_id]` KeyError. Because `KeyError` is neither `ClientError` nor `BotoCoreError`, it escaped the failover handler and could kill an entire batch's stdout. It was caught two turns later at L841, when I asked it to test the fallback model with real calls (L832) — the same test also showed a bad model id returns `ValidationException`, not `ResourceNotFoundException` as my spec assumed (L850).

### 2. Where the agent overruled me, and was right

L595 → L604

The agent had implemented the primary (Claude Sonnet 5) and fallback (Claude Sonnet 4.6) model ids as environment variables. There were some other variables in that block as well. At L595 I told it to drop those env vars and just set the default values as string literals. It complied with most of it but refused one part: "HARBOURMASTER_RULEBOOK has to stay — the eval suite's swap fixture drives it." It was right, as removing that one would have broken test_answers_follow_swapped_rulebook, which is the §2.5 proof that the rulebook is genuinely pure data.

### 3. Something I found that the agent never surfaced

L193 → L197 / L210 / L214

SPEC §2.2 grants the parser one structural assumption: heading syntax is markdown, not game content, so it may live in code. Nothing behind it ever checked the assumption is always true. I raised the case where a future rulebook edition changes heading convention and the parser finds zero markers, or far fewer than expected.

The agent traced it, and I assumed a bad parse would just mean no citations. But it found that with an empty index, §7.1 strips every citation and downgrades everything to abstention, but §2.5 still puts the full rulebook in the prompt, so the model answers correctly and gets stripped anyway. All 25 answers come back as abstentions so it looked like the agent was being careful but it was just the parser that stopped working. It then shipped SPEC §2.4