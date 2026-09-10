"""Parse a rulebook file into a section index.

Contains no game facts. Every pattern here is an assumption about *markdown*, not
about Harbourmaster: heading syntax, section-marker syntax, cross-reference syntax.
Swapping the rulebook for a different edition -- or a different game -- must not
require a change in this file. See SPEC.md 2.2.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from dataclasses import dataclass

DEFAULT_PATH = "RULEBOOK.md"
ENV_PATH = "HARBOURMASTER_RULEBOOK"

# SPEC 2.4 guard thresholds.
COVERAGE_MIN = 0.75
# SPEC 2.5: the whole document goes in every prompt, so an oversized rulebook
# invalidates the no-retrieval design. Warn loudly rather than silently truncate.
SIZE_WARN_CHARS = 100_000

# Any section-shaped token in the prose, used by the orphan-sigil guard.
SIGIL_TOKEN = re.compile(r"§\s*(\d+(?:\.\d+)?)")

# Any line that opens with an outline number, whatever decoration precedes it.
# Used only to detect structure that FAILED to parse -- never to build an index.
OUTLINE_AT_LINE_START = re.compile(
    r"^\s{0,3}(?:[#>*_\-]+\s*)?(?:§\s*)?(?:[A-Za-z]{3,12}\s+)?[*_]{0,2}(\d+\.\d+)(?!\d)(?!\.\d)"
)
# Three unparsed outline tokens is a broken convention; one is a stray decimal.
MAX_UNPARSED_OUTLINE = 3

# SPEC 2.4 tolerance ladder: cosmetic variation only. Emphasis wrappers and heading
# level are OPTIONAL within each variant, because heading style and subsection style
# vary independently -- pairing them rigidly means bolding one breaks the other.
# Structure is never inferred from bare numbers or heading text: a mis-parse is
# worse than a clean failure.
VARIANTS = (
    (
        "sigil",
        re.compile(r"^\s{0,3}#{1,6}\s*[*_]{0,2}\s*§\s*(\d+)\s*[*_]{0,2}\s*(.*)$"),
        re.compile(r"^\s{0,3}[*_]{0,2}\s*§\s*(\d+\.\d+)(?!\d)(?!\.\d)"),
    ),
    (
        "word-form",
        re.compile(r"^\s{0,3}#{1,6}\s*[*_]{0,2}\s*Section\s+(\d+)\s*[*_]{0,2}\s*(.*)$",
                   re.IGNORECASE),
        re.compile(r"^\s{0,3}[*_]{0,2}\s*Section\s+(\d+\.\d+)(?!\d)(?!\.\d)", re.IGNORECASE),
    ),
)


class RulebookError(Exception):
    """Precondition failure: the rulebook could not be loaded or parsed.

    SPEC 2.4 -- distinct from a per-question degradation, and fatal to the run.
    """

    def __init__(self, message: str, diagnostic: str = "") -> None:
        super().__init__(message)
        self.diagnostic = diagnostic


@dataclass(frozen=True)
class Section:
    id: str          # "§7.1"
    number: str      # "7.1"
    title: str       # "" for subsections, which carry no heading text
    text: str        # marker line through to the next marker: tables and lists included
    order: int       # document position, for stable citation ordering


@dataclass(frozen=True)
class Rulebook:
    path: str
    sha256: str
    raw: str
    sections: dict[str, Section]
    variant: str
    coverage: float

    @property
    def ids(self) -> list[str]:
        """Valid citation targets, in document order."""
        return [s.id for s in sorted(self.sections.values(), key=lambda s: s.order)]

    def order_of(self, section_id: str) -> int:
        s = self.sections.get(section_id)
        return s.order if s else 1 << 30

    def sort_ids(self, ids) -> list[str]:
        return sorted(set(ids), key=self.order_of)


def _markers(lines: list[str], heading_re, sub_re) -> list[tuple[str, str, int]]:
    """Return (id, title, line_index) for every marker the two patterns find."""
    found: list[tuple[str, str, int]] = []
    for i, line in enumerate(lines):
        m = heading_re.match(line)
        if m:
            found.append((f"§{m.group(1)}", (m.group(2) or "").strip(" *_#"), i))
            continue
        m = sub_re.match(line)
        if m:
            found.append((f"§{m.group(1)}", "", i))
    return found


def _build(lines: list[str], found) -> dict[str, Section]:
    """A section runs from its own marker to the next marker, or to EOF."""
    sections: dict[str, Section] = {}
    for order, (sid, title, start) in enumerate(found):
        end = found[order + 1][2] if order + 1 < len(found) else len(lines)
        text = "\n".join(lines[start:end]).rstrip()
        # A duplicate id means the file is malformed; first occurrence wins and the
        # collision is surfaced rather than silently overwritten.
        if sid in sections:
            raise RulebookError(
                f"duplicate section id {sid}",
                f"{sid} declared at lines {sections[sid].order} and {order}",
            )
        sections[sid] = Section(id=sid, number=sid[1:], title=title, text=text, order=order)
    return sections


def _coverage(lines: list[str], found) -> float:
    """Fraction of non-blank lines attributed to some section.

    Catches the case where a stray line happens to match while the real convention
    did not, leaving most of the document outside any section. It does NOT catch a
    partial parse -- sections tile the document by construction, so that is the
    orphan-sigil guard's job.
    """
    non_blank = sum(1 for line in lines if line.strip())
    if not non_blank:
        return 0.0
    first = found[0][2]
    attributed = sum(1 for line in lines[first:] if line.strip())
    return attributed / non_blank


def _orphan_sigils(raw: str, ids: set[str]) -> list[str]:
    """Section-shaped tokens in the text that are not valid ids.

    This is the partial-parse detector. If subsection markers stopped matching, the
    subsection references still in the prose become orphans. It doubles as a check
    for dangling cross-references in the rulebook itself, which is a defect to file.
    """
    seen: list[str] = []
    for m in SIGIL_TOKEN.finditer(raw):
        sid = f"§{m.group(1)}"
        if sid not in ids and sid not in seen:
            seen.append(sid)
    return seen


def _unparsed_outline(lines: list[str], ids: set[str]) -> list[str]:
    """Outline-numbered lines that did not become sections.

    This is the partial-parse detector for the case the orphan-sigil guard cannot
    see: a convention change that also strips the sigil, leaving top-level headings
    tiling the document and every subsection silently absorbed into its parent.
    Coverage cannot see it either, because sections tile by construction.

    Heuristic and deliberately narrow: it reports what failed to parse, and is never
    used to build an index.
    """
    missed: list[str] = []
    for line in lines:
        m = OUTLINE_AT_LINE_START.match(line)
        if m and f"§{m.group(1)}" not in ids and m.group(1) not in missed:
            missed.append(m.group(1))
    return missed


def _try_variant(lines, raw, name, heading_re, sub_re):
    """Return (rulebook_fields, None) on success or (None, reason) on guard failure."""
    found = _markers(lines, heading_re, sub_re)
    if not found:
        return None, "no section markers found"
    sections = _build(lines, found)
    cov = _coverage(lines, found)
    if cov < COVERAGE_MIN:
        return None, f"coverage {cov:.0%} below {COVERAGE_MIN:.0%} ({len(sections)} sections)"
    orphans = _orphan_sigils(raw, set(sections))
    if orphans:
        return None, (
            f"{len(orphans)} orphan section reference(s) not in the index: "
            + ", ".join(orphans[:8])
        )
    missed = _unparsed_outline(lines, set(sections))
    if len(missed) >= MAX_UNPARSED_OUTLINE:
        return None, (
            f"{len(missed)} outline-numbered line(s) did not parse as sections "
            f"({', '.join(missed[:8])}) -- convention looks changed, not absent"
        )
    return (sections, cov), None


def load(path: str | None = None, *, log=sys.stderr) -> Rulebook:
    """Load and parse exactly one rulebook. Never globs, never walks directories."""
    resolved = path or os.environ.get(ENV_PATH) or DEFAULT_PATH
    try:
        with open(resolved, encoding="utf-8") as handle:
            raw = handle.read()
    except OSError as exc:
        raise RulebookError(f"cannot read rulebook {resolved!r}", str(exc)) from exc

    if not raw.strip():
        raise RulebookError(f"rulebook {resolved!r} is empty")
    if len(raw) > SIZE_WARN_CHARS:
        print(
            f"warn: rulebook is {len(raw)} chars, over the {SIZE_WARN_CHARS} threshold; "
            "the whole-document prompt assumption (SPEC 2.5) may no longer hold",
            file=log,
        )

    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    lines = raw.splitlines()

    attempts: list[str] = []
    for name, heading_re, sub_re in VARIANTS:
        ok, reason = _try_variant(lines, raw, name, heading_re, sub_re)
        if ok:
            sections, cov = ok
            tops = sum(1 for s in sections if "." not in s)
            print(
                f"rulebook: {resolved} sha256={digest[:12]} variant={name} "
                f"sections={tops} subsections={len(sections) - tops} coverage={cov:.0%}",
                file=log,
            )
            return Rulebook(
                path=resolved, sha256=digest, raw=raw,
                sections=sections, variant=name, coverage=cov,
            )
        attempts.append(f"  variant {name}: {reason}")

    raise RulebookError(
        f"could not parse the section structure of {resolved!r}",
        "tried each heading convention and every one failed a guard:\n" + "\n".join(attempts),
    )
