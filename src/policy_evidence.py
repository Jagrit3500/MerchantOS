"""Fast, local policy evidence retrieval for first-page results.

The configured document directory is read at request time, so evidence reflects
the current policy files without waiting for an embedding model or external LLM.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from src import config


_TOKEN_RE = re.compile(r"[a-z0-9]+")
_HEADING_MAX_CHARS = getattr(
    config,
    "POLICY_EVIDENCE_HEADING_MAX_CHARS",
    config.ACTIVITY_TITLE_MAX_LENGTH,
)
_TERM_FREQUENCY_CAP = getattr(
    config,
    "POLICY_EVIDENCE_TERM_FREQUENCY_CAP",
    config.POLICY_EVIDENCE_RESULTS,
)
_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "do", "does", "for",
    "from", "how", "in", "is", "it", "of", "on", "or", "the", "their",
    "to", "under", "what", "when", "with",
}


def _tokens(text: str) -> list[str]:
    return [token for token in _TOKEN_RE.findall(text.lower()) if token not in _STOP_WORDS]


def _is_heading(text: str) -> bool:
    compact = text.strip()
    return bool(compact) and len(compact) <= _HEADING_MAX_CHARS and (
        compact.startswith(("SECTION ", "PARA "))
        or (compact.upper() == compact and any(char.isalpha() for char in compact))
    )


def _checked_at() -> str:
    return datetime.now().astimezone().strftime("%d %b %Y · %H:%M:%S %Z")


def _confidence(score: float) -> dict[str, float | str]:
    bounded = max(0.0, min(float(score), 1.0))
    if bounded >= config.CONFIDENCE_HIGH_THRESHOLD:
        label = "high"
    elif bounded >= config.SIMILARITY_THRESHOLD:
        label = "medium"
    elif bounded > 0:
        label = "low"
    else:
        label = "none"
    return {"score": round(bounded, 4), "label": label}


def _document_chunks(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    heading = "Document overview"
    chunks: list[dict[str, str]] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        one_line = " ".join(lines)
        # A document title followed by SOURCE/LAST VERIFIED metadata identifies the
        # source but is not substantive evidence for a merchant's case.
        if len(lines) > 1 and any(
            line.startswith(("SOURCE:", "SOURCES:", "REFERENCE:", "OFFICIAL URL:", "LAST VERIFIED:"))
            for line in lines[1:]
        ):
            heading = lines[0]
            continue
        if _is_heading(one_line):
            heading = one_line
            continue
        if len(one_line) < config.POLICY_EVIDENCE_MIN_CHARS:
            continue
        chunks.append({"source": path.name, "section": heading, "text": one_line})
    return chunks


def search_local_policy(query: str) -> dict:
    """Return query-ranked excerpts from the current local policy library."""
    docs_dir = Path(config.DOCS_DIR)
    paths = sorted(docs_dir.glob("*.txt")) if docs_dir.is_dir() else []
    chunks = [chunk for path in paths for chunk in _document_chunks(path)]
    query_terms = Counter(_tokens(query))
    if not chunks or not query_terms:
        return {
            "answer": "No matching local policy evidence is available yet.",
            "chunks": [],
            "source": "Local policy library",
            "llm_used": False,
            "confidence": _confidence(0),
            "confidence_method": "Weighted query-term coverage",
            "retrieval": "Local document search",
            "checked_at": _checked_at(),
        }

    document_frequency = Counter()
    chunk_terms: list[Counter] = []
    for chunk in chunks:
        terms = Counter(_tokens(f'{chunk["section"]} {chunk["text"]}'))
        chunk_terms.append(terms)
        document_frequency.update(terms.keys())

    total = len(chunks)
    ranked: list[tuple[float, dict[str, str]]] = []
    for chunk, terms in zip(chunks, chunk_terms):
        score = 0.0
        for term, query_count in query_terms.items():
            if terms[term]:
                inverse_frequency = math.log((total + 1) / (document_frequency[term] + 1)) + 1
                score += min(terms[term], _TERM_FREQUENCY_CAP) * query_count * inverse_frequency
        if score:
            ranked.append((score, chunk))

    ranked.sort(key=lambda item: (-item[0], item[1]["source"], item[1]["section"]))
    selected = ranked[: config.POLICY_EVIDENCE_RESULTS]
    excerpts = []
    for _, chunk in selected:
        text = chunk["text"]
        if len(text) > config.POLICY_EVIDENCE_EXCERPT_CHARS:
            text = text[: config.POLICY_EVIDENCE_EXCERPT_CHARS].rsplit(" ", 1)[0] + "..."
        excerpts.append(f'**{chunk["section"]}**  \n{text}  \n*Source: `{chunk["source"]}`*')

    answer = "\n\n".join(excerpts) if excerpts else (
        "No passage in the current local policy files matched this case. "
        "Add or update a policy document, then refresh."
    )
    sources = list(dict.fromkeys(chunk["source"] for _, chunk in selected))
    selected_terms = set()
    for _, chunk in selected:
        selected_terms.update(_tokens(f'{chunk["section"]} {chunk["text"]}'))
    query_weights = {
        term: (math.log((total + 1) / (document_frequency[term] + 1)) + 1) * count
        for term, count in query_terms.items()
    }
    total_query_weight = sum(query_weights.values())
    matched_query_weight = sum(
        weight for term, weight in query_weights.items() if term in selected_terms
    )
    coverage = matched_query_weight / total_query_weight if total_query_weight else 0.0
    return {
        "answer": answer,
        "chunks": [dict(chunk, relevance=score) for score, chunk in selected],
        "source": ", ".join(sources) if sources else "Local policy library",
        "llm_used": False,
        "confidence": _confidence(coverage),
        "confidence_method": "Weighted query-term coverage",
        "retrieval": "Local document search",
        "checked_at": _checked_at(),
    }


def get_policy_evidence(
    query: str,
    semantic: bool = True,
    reconnect_index: bool = False,
) -> dict:
    """Return current extractive evidence with a consistent confidence contract.

    Semantic retrieval supplies source selection and cosine confidence. The text
    shown to the user remains extractive from the current local policy files so a
    fluent model cannot add a claim that is absent from its citation.
    """
    local = search_local_policy(query)
    if not semantic:
        local["status"] = "Matched against the current local policy files."
        return local

    try:
        from src.retriever import retrieve_and_filter

        chunks, is_answerable, _ = retrieve_and_filter(
            query,
            reconnect=reconnect_index,
        )
    except Exception:
        local["status"] = "Semantic search was unavailable; current local policy matches are shown."
        return local

    if not chunks or not is_answerable:
        local["status"] = "Semantic search found no qualifying indexed passage; current local policy matches are shown."
        return local

    top_score = float(chunks[0].get("similarity") or 0)
    return {
        "answer": local["answer"],
        "chunks": chunks,
        "source": local["source"],
        "llm_used": False,
        "confidence": _confidence(top_score),
        "confidence_method": "Top cosine similarity",
        "retrieval": "Semantic source recheck",
        "checked_at": _checked_at(),
        "status": (
            f"Rechecked {len(chunks)} indexed policy passage{'s' if len(chunks) != 1 else ''} "
            "for semantic relevance. The evidence displayed below is extracted from the current "
            "local source files listed above."
        ),
    }
