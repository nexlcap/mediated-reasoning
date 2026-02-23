"""Cross-session project memory: living brief + append-only session logs."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

QAPair = Tuple[str, str]  # (question, answer)

BRIEF_TEMPLATE = """\
## Stage
<!-- e.g. Idea validation — pre-revenue, solo founder -->

## Locked decisions
<!-- e.g. B2B SaaS, not consumer -->

## Open questions
<!-- e.g. Pricing model: usage-based vs. flat? -->

## Next actions
<!-- e.g. Validate willingness-to-pay with 5 users -->
"""

BRIEF_SYSTEM = (
    "You maintain a living project brief for a startup idea. "
    "Rewrite it to reflect the current state based on the session below. "
    "Keep all four sections (Stage, Locked decisions, Open questions, Next actions). "
    "Stay under 1000 tokens. Return ONLY markdown — no preamble, no code fences."
)


class ProjectMemory:
    def __init__(self, project_dir: str) -> None:
        self.project_dir = Path(project_dir).expanduser().resolve()
        self.brief_path = self.project_dir / "brief.md"
        self.sessions_dir = self.project_dir / "sessions"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> str:
        """Ensure dirs + brief exist; return current brief text."""
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        if not self.brief_path.exists():
            self.brief_path.write_text(BRIEF_TEMPLATE, encoding="utf-8")
        return self.brief_path.read_text(encoding="utf-8")

    def brief_as_context(self) -> str:
        """Return brief formatted as context string for injection into prompts."""
        brief = self.brief_path.read_text(encoding="utf-8").strip()
        return f"Project brief:\n{brief}"

    def save_session(
        self,
        analysis,
        qa_pairs: List[QAPair],
    ) -> str:
        """Append session log to sessions/YYYY-MM-DD.md; return file path."""
        today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        session_file = self.sessions_dir / f"{today}.md"

        timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M")
        lines: List[str] = [f"## Session {timestamp}"]

        problem = getattr(analysis, "problem", None) or ""
        lines.append(f"**Problem:** {problem}")

        synthesis = getattr(analysis, "synthesis", None) or ""
        if synthesis:
            lines.append(f"\n**Synthesis:** {synthesis}")

        recs = getattr(analysis, "recommendations", None) or []
        if recs:
            lines.append("\n**Recommendations:**")
            for rec in recs:
                rec_text = rec if isinstance(rec, str) else str(rec)
                lines.append(f"- {rec_text}")

        if qa_pairs:
            lines.append("\n**Follow-ups:**")
            for q, a in qa_pairs:
                lines.append(f"Q: {q}")
                lines.append(f"A: {a}")
                lines.append("")

        block = "\n".join(lines) + "\n\n---\n\n"

        with open(session_file, "a", encoding="utf-8") as f:
            f.write(block)

        return str(session_file)

    def update_brief(self, client, analysis, qa_pairs: List[QAPair]) -> str:
        """Use LLM to rewrite brief.md; return new brief text."""
        current_brief = self.brief_path.read_text(encoding="utf-8")

        problem = getattr(analysis, "problem", None) or ""
        synthesis = getattr(analysis, "synthesis", None) or ""
        recs = getattr(analysis, "recommendations", None) or []

        recs_text = ""
        if recs:
            recs_text = "\n".join(f"- {r}" for r in recs)

        qa_text = ""
        if qa_pairs:
            qa_text = "\n".join(f"Q: {q}\nA: {a}" for q, a in qa_pairs)

        user_prompt = f"""\
Current brief:
{current_brief}

---
Latest session
Problem: {problem}

Synthesis: {synthesis}

Recommendations:
{recs_text}

Follow-up Q&A:
{qa_text}
""".strip()

        new_brief = client.chat(BRIEF_SYSTEM, user_prompt)
        if new_brief:
            self.brief_path.write_text(new_brief.strip() + "\n", encoding="utf-8")
        return new_brief
