from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class KnowledgeDocument:
    path: str
    title: str
    domain: str
    source: str
    status: str
    keywords: tuple[str, ...]
    related: tuple[str, ...]
    text: str


@dataclass(frozen=True)
class KnowledgeChunk:
    document: KnowledgeDocument
    heading: str
    text: str
    index: int
    terms: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class KnowledgeHit:
    chunk: KnowledgeChunk
    score: float
    matched_terms: tuple[str, ...]


class KnowledgeRetriever:
    """Small dependency-free retrieval layer for official and learned knowledge.

    Official documents are trusted reference material. Learned documents are
    intentionally kept separate and receive a lower default trust score.
    Conflicted learned documents are excluded from normal retrieval so an
    unresolved contradiction cannot silently influence the analyst as a rule.
    """

    STOPWORDS = frozenset(
        {
            "и", "или", "в", "во", "на", "с", "со", "к", "ко", "из", "у", "по",
            "для", "от", "до", "за", "как", "что", "это", "этот", "эта", "эти",
            "при", "если", "то", "же", "ли", "не", "ни", "а", "но", "да", "о",
            "об", "про", "можно", "нужно", "есть", "быть", "так", "его", "её",
            "их", "он", "она", "они", "мы", "вы", "я", "ты",
        }
    )

    def __init__(self, root: str | Path = "data/knowledge", chunk_size: int = 1800):
        self.root = Path(root)
        self.chunk_size = max(500, chunk_size)
        self.documents: list[KnowledgeDocument] = []
        self.chunks: list[KnowledgeChunk] = []
        self._load()

    def reload(self) -> None:
        self.documents.clear()
        self.chunks.clear()
        self._load()

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        domain: str | None = None,
        source: str | None = None,
        include_learned: bool = True,
        include_conflicted: bool = False,
    ) -> list[KnowledgeHit]:
        query_terms = self._terms(query)
        if not query_terms:
            return []

        hits: list[KnowledgeHit] = []
        for chunk in self.chunks:
            document = chunk.document
            if domain and document.domain != domain:
                continue
            if source and document.source != source:
                continue
            if not include_learned and document.source == "learned":
                continue
            if document.source == "learned" and document.status == "conflicted" and not include_conflicted:
                continue

            matched = query_terms & chunk.terms
            if not matched:
                continue

            score = self._score(query_terms, matched, chunk)
            hits.append(KnowledgeHit(chunk=chunk, score=score, matched_terms=tuple(sorted(matched))))

        hits.sort(key=lambda hit: (-hit.score, hit.chunk.document.path, hit.chunk.index))
        return hits[: max(1, top_k)]

    def build_context(
        self,
        query: str,
        *,
        top_k: int = 5,
        max_chars: int = 9000,
        domain: str | None = None,
        include_learned: bool = True,
        include_conflicted: bool = False,
    ) -> str:
        hits = self.search(
            query,
            top_k=top_k,
            domain=domain,
            include_learned=include_learned,
            include_conflicted=include_conflicted,
        )
        if not hits:
            return ""

        blocks: list[str] = []
        used = 0
        for hit in hits:
            if hit.chunk.document.source == "official":
                source_label = "OFFICIAL"
            elif hit.chunk.document.status == "conflicted":
                source_label = "LEARNED-CONFLICT"
            else:
                source_label = "LEARNED"
            block = (
                f"[SOURCE={source_label}]\n"
                f"[STATUS={hit.chunk.document.status}]\n"
                f"[FILE={hit.chunk.document.path}]\n"
                f"[SECTION={hit.chunk.heading}]\n"
                f"{hit.chunk.text.strip()}"
            )
            if used and used + len(block) + 2 > max_chars:
                break
            if not used and len(block) > max_chars:
                block = block[:max_chars]
            blocks.append(block)
            used += len(block) + 2

        return "\n\n---\n\n".join(blocks)

    def build_qwen_prompt_context(
        self,
        query: str,
        *,
        top_k: int = 5,
        max_chars: int = 9000,
        domain: str | None = None,
        include_conflicted: bool = False,
    ) -> str:
        context = self.build_context(
            query,
            top_k=top_k,
            max_chars=max_chars,
            domain=domain,
            include_learned=True,
            include_conflicted=include_conflicted,
        )
        if not context:
            return "No relevant knowledge was retrieved."
        return (
            "Use the retrieved knowledge as reference context. Official knowledge "
            "is trusted documentation; learned knowledge consists of observations "
            "and hypotheses and must not override explicit official rules. "
            "Conflicted learned claims are excluded unless explicitly requested.\n\n"
            + context
        )

    def _load(self) -> None:
        if not self.root.exists():
            return

        for path in sorted(self.root.rglob("*.md")):
            relative = path.relative_to(self.root).as_posix()
            source = "learned" if relative.startswith("learned/") else "official"
            text = path.read_text(encoding="utf-8")
            metadata, body = self._parse_frontmatter(text)
            domain = metadata.get("domain") or self._infer_domain(relative)
            title = metadata.get("id") or path.stem
            keywords = tuple(self._split_metadata(metadata.get("keywords", "")))
            related = tuple(self._split_metadata(metadata.get("related", "")))
            document = KnowledgeDocument(
                path=relative,
                title=title,
                domain=domain,
                source=metadata.get("source", source),
                status=metadata.get("status", "unknown"),
                keywords=keywords,
                related=related,
                text=body,
            )
            self.documents.append(document)
            self.chunks.extend(self._chunk_document(document))

    def _chunk_document(self, document: KnowledgeDocument) -> list[KnowledgeChunk]:
        lines = document.text.splitlines()
        sections: list[tuple[str, list[str]]] = []
        heading = document.title
        current: list[str] = []

        for line in lines:
            if line.startswith("#"):
                if current and any(item.strip() for item in current):
                    sections.append((heading, current))
                    current = []
                heading = line.lstrip("#").strip() or document.title
            else:
                current.append(line)
        if current and any(item.strip() for item in current):
            sections.append((heading, current))

        chunks: list[KnowledgeChunk] = []
        index = 0
        for section_heading, section_lines in sections:
            section_text = "\n".join(section_lines).strip()
            if not section_text:
                continue
            for piece in self._split_text(section_text):
                terms = self._terms(
                    " ".join(
                        [
                            document.title,
                            document.domain,
                            " ".join(document.keywords),
                            " ".join(document.related),
                            section_heading,
                            piece,
                        ]
                    )
                )
                chunks.append(
                    KnowledgeChunk(
                        document=document,
                        heading=section_heading,
                        text=piece,
                        index=index,
                        terms=frozenset(terms),
                    )
                )
                index += 1
        return chunks

    def _split_text(self, text: str) -> list[str]:
        if len(text) <= self.chunk_size:
            return [text]

        paragraphs = re.split(r"\n\s*\n", text)
        chunks: list[str] = []
        current = ""
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
            if len(candidate) <= self.chunk_size:
                current = candidate
                continue
            if current:
                chunks.append(current)
                current = ""
            while len(paragraph) > self.chunk_size:
                cut = paragraph.rfind(" ", 0, self.chunk_size)
                if cut < self.chunk_size // 2:
                    cut = self.chunk_size
                chunks.append(paragraph[:cut].strip())
                paragraph = paragraph[cut:].strip()
            current = paragraph
        if current:
            chunks.append(current)
        return chunks

    def _score(self, query_terms: set[str], matched: set[str], chunk: KnowledgeChunk) -> float:
        coverage = len(matched) / max(1, len(query_terms))
        density = len(matched) / max(1, len(chunk.terms))
        exact_bonus = 0.0
        query_text = " ".join(sorted(query_terms))
        chunk_text = chunk.text.lower()
        if query_text and query_text in chunk_text:
            exact_bonus = 2.0

        metadata_bonus = 0.0
        metadata_terms = self._terms(
            " ".join(
                [
                    chunk.document.title,
                    chunk.document.domain,
                    " ".join(chunk.document.keywords),
                ]
            )
        )
        metadata_bonus += len(matched & metadata_terms) * 0.75

        trust_bonus = 1.0 if chunk.document.source == "official" else 0.35
        return 6.0 * coverage + 2.0 * math.sqrt(density) + exact_bonus + metadata_bonus + trust_bonus

    @classmethod
    def _terms(cls, text: str) -> set[str]:
        normalized = text.lower().replace("ё", "е")
        raw = re.findall(r"[a-zа-я0-9_/-]{2,}", normalized, re.IGNORECASE)
        return {term for term in raw if term not in cls.STOPWORDS}

    @staticmethod
    def _split_metadata(value: str) -> list[str]:
        if not value:
            return []
        value = value.replace("[", "").replace("]", "")
        return [item.strip(" '\"") for item in re.split(r",|;", value) if item.strip(" '\"")]

    @staticmethod
    def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
        if not text.startswith("---\n"):
            return {}, text
        end = text.find("\n---", 4)
        if end < 0:
            return {}, text
        raw = text[4:end]
        metadata: dict[str, str] = {}
        current_key = None
        for line in raw.splitlines():
            if line.startswith("  - ") and current_key:
                metadata[current_key] = f"{metadata.get(current_key, '')},{line[4:].strip()}"
                continue
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            current_key = key.strip()
            metadata[current_key] = value.strip().strip("'\"")
        return metadata, text[end + 4 :].lstrip("\n")

    @staticmethod
    def _infer_domain(relative: str) -> str:
        parts = relative.split("/")
        if len(parts) >= 2 and parts[0] in {"official", "learned"}:
            return parts[1] if len(parts) > 2 else "general"
        return parts[0] if parts else "general"
