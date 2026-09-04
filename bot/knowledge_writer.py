import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any


class KnowledgeWriter:
    def __init__(self, root: str = "data/knowledge/learned", evidence_path: str = "data/knowledge/learned/.evidence.json"):
        self.root = Path(root)
        self.evidence_path = Path(evidence_path)
        self.root.mkdir(parents=True, exist_ok=True)
        self.evidence_path.parent.mkdir(parents=True, exist_ok=True)
        self.records = self._load_records()

    def write_candidates(
        self,
        candidates: list[dict[str, Any]],
        account_id: str,
        observation_id: str = "",
    ) -> list[Path]:
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
            record = self._record_observation(
                digest=digest,
                claim=claim,
                candidate=candidate,
                account_id=account_id,
                observation_id=observation_id,
                confidence=confidence,
            )

            directory = self.root / domain
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / f"{kind}-{digest}.md"
            content = self._render(
                candidate=candidate,
                claim=claim,
                confidence=record["confidence"],
                status=record["status"],
                account_id=account_id,
                evidence_lines=self._evidence_lines(record),
                conditions=str(record.get("conditions", candidate.get("conditions", ""))).strip(),
                consequences=str(record.get("consequences", candidate.get("consequences", ""))).strip(),
                exceptions=str(record.get("exceptions", candidate.get("exceptions", ""))).strip(),
                digest=digest,
                record=record,
            )
            path.write_text(content, encoding="utf-8")
            written.append(path)

        self._save_records()
        return written

    def _record_observation(
        self,
        digest: str,
        claim: str,
        candidate: dict[str, Any],
        account_id: str,
        observation_id: str,
        confidence: float,
    ) -> dict[str, Any]:
        record = self.records.setdefault(
            digest,
            {
                "claim": claim,
                "domain": self._slug(candidate.get("domain", "general")) or "general",
                "type": self._slug(candidate.get("type", "observation")) or "observation",
                "mechanic_key": self._slug(candidate.get("mechanic_key", "")),
                "conditions": str(candidate.get("conditions", "")).strip(),
                "consequences": str(candidate.get("consequences", "")).strip(),
                "exceptions": str(candidate.get("exceptions", "")).strip(),
                "related": self._normalize_list(candidate.get("related", [])),
                "observations": [],
                "accounts": [],
                "confidence": 0.0,
                "status": "hypothesis",
                "conflicts": [],
                "conflicting_claims": [],
            },
        )

        if not record.get("mechanic_key"):
            record["mechanic_key"] = self._slug(candidate.get("mechanic_key", ""))
        for field in ("conditions", "consequences", "exceptions"):
            if not record.get(field) and candidate.get(field):
                record[field] = str(candidate.get(field)).strip()
        if not record.get("related"):
            record["related"] = self._normalize_list(candidate.get("related", []))

        observation_id = observation_id or hashlib.sha1(
            f"{account_id}|{claim}|{time.time_ns()}".encode("utf-8")
        ).hexdigest()[:16]
        known_ids = {item.get("id") for item in record["observations"]}
        if observation_id not in known_ids:
            record["observations"].append(
                {
                    "id": observation_id,
                    "account_id": account_id,
                    "timestamp": time.time(),
                    "confidence": confidence,
                    "evidence": self._normalize_list(candidate.get("evidence", [])),
                }
            )

        if account_id not in record["accounts"]:
            record["accounts"].append(account_id)

        relation = str(candidate.get("relation", "new")).strip().lower()
        if relation == "contradicts":
            self._mark_conflicts(record, candidate)

        observations = record["observations"]
        average_confidence = sum(item["confidence"] for item in observations) / max(1, len(observations))
        record["confidence"] = min(0.99, max(average_confidence, confidence))

        independent_accounts = len(record["accounts"])
        observation_count = len(observations)
        if record.get("conflicts"):
            record["status"] = "conflicted"
        elif observation_count >= 3 and independent_accounts >= 2 and record["confidence"] >= 0.70:
            record["status"] = "confirmed"
        elif observation_count >= 2 and record["confidence"] >= 0.80:
            record["status"] = "candidate"
        else:
            record["status"] = "hypothesis"
        return record

    def _mark_conflicts(self, record: dict[str, Any], candidate: dict[str, Any]) -> None:
        targets = self._normalize_list(candidate.get("conflicts_with", []))
        mechanic_key = record.get("mechanic_key", "")
        if not targets or not mechanic_key:
            return

        for target in targets:
            target_digest = hashlib.sha1(target.lower().encode("utf-8")).hexdigest()[:12]
            target_record = self.records.get(target_digest)
            if not target_record or target_record is record:
                continue
            if target_record.get("mechanic_key") != mechanic_key:
                continue
            if target_digest not in record["conflicts"]:
                record["conflicts"].append(target_digest)
            if record.get("claim") not in target_record.setdefault("conflicting_claims", []):
                target_record["conflicting_claims"].append(record["claim"])
            record_digest = self._digest_for_record(record)
            if record_digest not in target_record.setdefault("conflicts", []):
                target_record["conflicts"].append(record_digest)
            target_record["status"] = "conflicted"
            self._write_record_file(target_record, "conflict-detected")

    def _write_record_file(self, record: dict[str, Any], account_id: str) -> Path:
        domain = self._slug(record.get("domain", "general")) or "general"
        kind = self._slug(record.get("type", "observation")) or "observation"
        digest = self._digest_for_record(record)
        directory = self.root / domain
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{kind}-{digest}.md"
        candidate = {
            "domain": domain,
            "type": kind,
            "conditions": record.get("conditions", ""),
            "consequences": record.get("consequences", ""),
            "exceptions": record.get("exceptions", ""),
            "related": record.get("related", []),
        }
        path.write_text(
            self._render(
                candidate=candidate,
                claim=str(record.get("claim", "")),
                confidence=float(record.get("confidence", 0.0)),
                status=str(record.get("status", "hypothesis")),
                account_id=account_id,
                evidence_lines=self._evidence_lines(record),
                conditions=str(record.get("conditions", "")).strip(),
                consequences=str(record.get("consequences", "")).strip(),
                exceptions=str(record.get("exceptions", "")).strip(),
                digest=digest,
                record=record,
            ),
            encoding="utf-8",
        )
        return path

    def _digest_for_record(self, record: dict[str, Any]) -> str:
        claim = str(record.get("claim", "")).strip()
        return hashlib.sha1(claim.lower().encode("utf-8")).hexdigest()[:12] if claim else ""

    def _evidence_lines(self, record: dict[str, Any]) -> str:
        lines = []
        for item in record["observations"][-12:]:
            evidence = item.get("evidence") or ["Runtime observation by the learning agent."]
            detail = "; ".join(str(value).strip() for value in evidence if str(value).strip())
            lines.append(
                f"- [{item.get('account_id', 'unknown')}] {detail} "
                f"(confidence {float(item.get('confidence', 0.0)):.2f})"
            )
        return "\n".join(lines) or "- Runtime observation by the learning agent."

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
        record: dict[str, Any],
    ) -> str:
        domain = self._slug(candidate.get("domain", "general")) or "general"
        kind = self._slug(candidate.get("type", "observation")) or "observation"
        related = candidate.get("related", [])
        if isinstance(related, str):
            related = [related]
        related_yaml = "\n".join(f"  - {self._yaml_value(item)}" for item in related if str(item).strip())
        if not related_yaml:
            related_yaml = "  []"
        conflicts_yaml = "\n".join(f"  - {self._yaml_value(item)}" for item in record.get("conflicts", []))
        if not conflicts_yaml:
            conflicts_yaml = "  []"

        sections = [
            f"# {claim}",
            "",
            f"**Status:** `{status}`  ",
            f"**Confidence:** `{confidence:.2f}`  ",
            f"**Supporting observations:** `{len(record['observations'])}`  ",
            f"**Independent accounts:** `{len(record['accounts'])}`  ",
            f"**Observed by account:** `{account_id}`  ",
            f"**Recorded at:** `{time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}`",
            "",
        ]
        if record.get("conflicts"):
            sections.extend([
                "## Conflict",
                "",
                "This learned claim conflicts with another learned claim sharing the same mechanic key. Neither claim is treated as authoritative until additional evidence resolves the conflict.",
                "",
            ])
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
            f"observations: {len(record['observations'])}\n"
            f"accounts: {len(record['accounts'])}\n"
            f"mechanic_key: {self._yaml_value(record.get('mechanic_key', ''))}\n"
            "keywords:\n"
            f"  - {self._yaml_value(domain)}\n"
            f"  - {self._yaml_value(kind)}\n"
            "related:\n"
            f"{related_yaml}\n"
            "conflicts:\n"
            f"{conflicts_yaml}\n"
            "---\n\n"
            + "\n".join(sections)
        )

    def _load_records(self) -> dict[str, dict[str, Any]]:
        if not self.evidence_path.exists():
            return {}
        try:
            data = json.loads(self.evidence_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_records(self) -> None:
        temporary = self.evidence_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.records, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.evidence_path)

    @staticmethod
    def _normalize_list(value: Any) -> list[str]:
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

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
