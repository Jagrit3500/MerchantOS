import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
from src import config


def extract_cited_pages(answer: str) -> list[int]:
    """
    Extract all page numbers cited in answer like [Page 3].
    """
    pattern = r'\[Page (\d+)\]'
    matches = re.findall(pattern, answer)
    return list(set(int(m) for m in matches))


def extract_cited_sources(answer: str) -> list[str]:
    """Extract filenames from citations such as [Source: policy.txt]."""
    matches = re.findall(r"\[Source:\s*([^,\]]+)", answer, flags=re.IGNORECASE)
    return list(dict.fromkeys(match.strip() for match in matches if match.strip()))


def get_retrieved_pages(chunks: list[dict]) -> list[int]:
    """
    Get all page numbers from retrieved chunks.
    """
    return list(set(chunk["page"] for chunk in chunks))


def validate_citations(answer: str, chunks: list[dict]) -> dict:
    """
    Validate that cited pages actually exist in retrieved chunks.
    """
    refusals = [
        "I could not find this information in the uploaded PDF.",
        "I could not find this information in the knowledge base.",
        "No relevant information found in the knowledge base."
    ]
    if any(r.lower() in answer.lower() for r in refusals):
        return {
            "is_valid": True,
            "is_refusal": True,
            "cited_pages": [],
            "retrieved_pages": [],
            "invalid_pages": [],
            "missing_citations": False,
            "message": "Refusal response — no citation needed"
        }

    cited_pages = extract_cited_pages(answer)
    cited_sources = extract_cited_sources(answer)
    retrieved_pages = get_retrieved_pages(chunks)
    retrieved_sources = {str(chunk.get("source", "")) for chunk in chunks}
    missing_citations = not cited_pages and not cited_sources
    invalid_pages = [p for p in cited_pages if p not in retrieved_pages]
    invalid_sources = [source for source in cited_sources if source not in retrieved_sources]
    is_valid = not missing_citations and not invalid_pages and not invalid_sources

    return {
        "is_valid": is_valid,
        "is_refusal": False,
        "cited_pages": cited_pages,
        "retrieved_pages": retrieved_pages,
        "invalid_pages": invalid_pages,
        "cited_sources": cited_sources,
        "invalid_sources": invalid_sources,
        "missing_citations": missing_citations,
        "message": _get_validation_message(is_valid, missing_citations, invalid_pages, invalid_sources)
    }


def _get_validation_message(
    is_valid: bool,
    missing_citations: bool,
    invalid_pages: list[int],
    invalid_sources: list[str],
) -> str:
    if is_valid:
        return "Citations validated successfully"
    if missing_citations:
        return "Answer is missing page citations"
    if invalid_pages:
        return f"Answer cites pages not in retrieved chunks: {invalid_pages}"
    if invalid_sources:
        return f"Answer cites sources not in retrieved chunks: {invalid_sources}"
    return "Citation validation failed"


def get_confidence_label(
    chunks: list[dict],
    threshold: float = config.SIMILARITY_THRESHOLD
) -> dict:
    """
    Return confidence score and label based on top similarity.
    Uses active threshold from UI slider.
    """
    if not chunks:
        return {"score": 0.0, "label": "none"}

    top_score = chunks[0]["similarity"]

    if top_score >= config.CONFIDENCE_HIGH_THRESHOLD:
        label = "high"
    elif top_score >= threshold:
        label = "medium"
    else:
        label = "low"

    return {
        "score": round(top_score, 4),
        "label": label
    }


def build_final_response(
    answer: str,
    chunks: list[dict],
    is_answerable: bool,
    threshold: float = config.SIMILARITY_THRESHOLD
) -> dict:
    refusal = "I could not find this information in the uploaded PDF."
    validation = validate_citations(answer, chunks)
    confidence = get_confidence_label(chunks, threshold)

    # Override is_answerable if LLM returned refusal text
    if refusal in answer:
        is_answerable = False

    if not validation["is_valid"] and not validation["is_refusal"]:
        return {
            "answer": refusal,
            "is_answerable": False,
            "confidence": {"score": 0.0, "label": "none"},
            "validation": validation,
            "chunks": chunks,
            "evidence_pages": []
        }

    return {
        "answer": answer,
        "is_answerable": is_answerable,
        "confidence": confidence if is_answerable else {"score": 0.0, "label": "none"},
        "validation": validation,
        "chunks": chunks if is_answerable else [],
        "evidence_pages": validation["retrieved_pages"] if is_answerable else []
    }
