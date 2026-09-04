import hashlib
import re
import time
from pathlib import Path
from typing import Any


class KnowledgeWriter:
    def __init__(self, root: str = "data/knowledge/learned"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def write_candidates(self, candidates: list[dict[str, Any]], account_id: str) -> list[Path]:
        written = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            claim = str(candidate.get("claim", "")).strip()
            if not claim:
                continue
            confidence = self._confidence(candidate.get("confidence", 0.0))
            if confidence < 0.55:
                continue

            domain = self._slug(candidate.get("domain", "general")) or "general"
            kind = self._slug(candidate.get("type", "observation")) or "observation"
            digest = hashlib.sha1(claim.lower().encode("utf-8")).hexdigest()[:12]
            directory = self.root / domain
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / f"{kind}-{digest}.md"

            evidence = candidate.get("evidence", [])
            if isinstance(evidence, str):
                evidence = [evidence]
            evidence_lines = "\n".join(f"- {str(item).strip()}" for item in evidence if str(item).strip())
            if not evidence_lines:
                evidence_lines = "- Runtime observation by the learning agent."

            conditions = str(candidate.get("conditions", "")).strip()
            consequences = str(candidate.get("consequences", "")).strip()
            exceptions = str(candidate.get("exceptions", "")).strip()
            status = str(candidate.get("status", "hypothesis")).strip().lower()
            if status not in {"hypothesis", "candidate", "confirmed"}:
                status = "hypothesis"
            if status == "confirmed":
                status = "hypothesis"

            content = self._render(
                candidate=candidate,
                claim=claim,
                confidence=confidence,
                status=status,
                account_id=account_id,
                evidence_lines=evidence_lines,
                conditions=conditions,
                consequences=consequences,
                exceptions=exceptions,
                digest=digest,
            )
            path.write_text(content, encoding="utf-8")
            written.append(path)
        return written

    def _render(
        self,
        candidate: dict[str, Any],
        claim: str,
        confidence: float,
        status: str,
        account_id: str,
        evidence_lines: str,
        conditions: str,
        consequences: str,
        exceptions: str,
        digest: str,
    ) -> str:
        domain = self._slug(candidate.get("domain", "general")) or "general"
        kind = self._slug(candidate.get("type", "observation")) or "observation"
        related = candidate.get("related", [])
        if isinstance(related, str):
            related = [related]
        related_yaml = "\n".join(f"  - {self._yaml_value(item)}" for item in related if str(item).strip())
        if not related_yaml:
            related_yaml = "  []"

        sections = [
            f"# {claim}",
            "",
            f"**Status:** `{status}`  ",
            f"**Confidence:** `{confidence:.2f}`  ",
            f"**Observed by account:** `{account_id}`  ",
            f"**Recorded at:** `{time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}`",
            "",
        ]
        if conditions:
            sections.extend(["## Conditions", "", conditions, ""])
        if consequences:
            sections.extend(["## Consequences", "", consequences, ""])
        if exceptions:
            sections.extend(["## Exceptions", "", exceptions, ""])
        sections.extend(["## Evidence", "", evidence_lines, ""])
        return (
            "---\n"
            f"id: learned-{domain}-{kind}-{digest}\n"
            f"type: {self._yaml_value(kind)}\n"
            f"domain: {self._yaml_value(domain)}\n"
            "source: learned\n"
            f"status: {self._yaml_value(status)}\n"
            f"confidence: {confidence:.2f}\n"
            "keywords:\n"
            f"  - {self._yaml_value(domain)}\n"
            f"  - {self._yaml_value(kind)}\n"
            "related:\n"
            f"{related_yaml}\n"
            "---\n\n"
            + "\n".join(sections)
        )

    @staticmethod
    def _confidence(value: Any) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _slug(value: Any) -> str:
        value = str(value).strip().lower().replace(" ", "_")
        return re.sub(r"[^a-zа-яё0-9_-]", "", value)

    @staticmethod
    def _yaml_value(value: Any) -> str:
        text = str(value).strip().replace("\n", " ").replace("\"", "\\\"")
        return f'"{text}"'
