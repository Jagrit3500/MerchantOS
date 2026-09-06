import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
from src.config import SIMILARITY_THRESHOLD


def extract_cited_pages(answer: str) -> list[int]:
    """
    Extract all page numbers cited in answer like [Page 3].
    """
    pattern = r'\[Page (\d+)\]'
    matches = re.findall(pattern, answer)
    return list(set(int(m) for m in matches))


def get_retrieved_pages(chunks: list[dict]) -> list[int]:
    """
    Get all page numbers from retrieved chunks.
    """
    return list(set(chunk["page"] for chunk in chunks))


def validate_citations(answer: str, chunks: list[dict]) -> dict:
    """
    Validate that cited pages actually exist in retrieved chunks.
    """
    refusal = "I could not find this information in the uploaded PDF."

    if refusal in answer:
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
    retrieved_pages = get_retrieved_pages(chunks)
    missing_citations = len(cited_pages) == 0
    invalid_pages = [p for p in cited_pages if p not in retrieved_pages]
    is_valid = not missing_citations and len(invalid_pages) == 0

    return {
        "is_valid": is_valid,
        "is_refusal": False,
        "cited_pages": cited_pages,
        "retrieved_pages": retrieved_pages,
        "invalid_pages": invalid_pages,
        "missing_citations": missing_citations,
        "message": _get_validation_message(is_valid, missing_citations, invalid_pages)
    }


def _get_validation_message(
    is_valid: bool,
    missing_citations: bool,
    invalid_pages: list[int]
) -> str:
    if is_valid:
        return "Citations validated successfully"
    if missing_citations:
        return "Answer is missing page citations"
    if invalid_pages:
        return f"Answer cites pages not in retrieved chunks: {invalid_pages}"
    return "Citation validation failed"


def get_confidence_label(
    chunks: list[dict],
    threshold: float = SIMILARITY_THRESHOLD
) -> dict:
    """
    Return confidence score and label based on top similarity.
    Uses active threshold from UI slider.
    """
    if not chunks:
        return {"score": 0.0, "label": "none"}

    top_score = chunks[0]["similarity"]

    if top_score >= 0.80:
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
    threshold: float = SIMILARITY_THRESHOLD
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