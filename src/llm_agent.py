"""
LLM Agent for MerchantOS — RAG-grounded answers from knowledge base.
Tries Groq LLM first. If unavailable (network issue, API error),
falls back to directly presenting the top retrieved chunks as structured evidence.
This ensures the app is ALWAYS useful regardless of LLM availability.
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import config

from src.retriever import retrieve_and_filter, format_context
from src.citation_validator import get_confidence_label, validate_citations

_groq_client = None
_groq_available = False

def _init_groq():
    global _groq_client, _groq_available
    key = config.GROQ_API_KEY.strip()
    if not key or key.lower().startswith(("your_", "replace_")):
        return False
    try:
        from groq import Groq
        _groq_client = Groq(api_key=key)
        _groq_available = True
        return True
    except Exception:
        _groq_client = None
        _groq_available = False
        return False

_init_groq()

SYSTEM_PROMPT = """You are a strict RBI-grounded compliance assistant for Indian merchants.

Your rules:
1. Answer ONLY using the provided context below.
2. Every factual claim MUST include a citation like [Page X] or [Source: filename].
3. If the answer is not present in the context, say: "I could not find this information in the knowledge base."
4. Never use outside knowledge. Never guess.
5. Be concise and factual. Help the merchant understand what they need to do.
6. Focus on actionable advice: what documents to submit, what rights the merchant has, what payment aggregators can and cannot demand under RBI directives.
"""


def _format_fallback_answer(chunks: list[dict], query: str) -> str:
    """
    When Groq is unavailable, format retrieved chunks as a clean, structured answer.
    This ensures the app always delivers value from the knowledge base.
    """
    if not chunks:
        return "No relevant information found in the knowledge base for this query."

    lines = ["**Relevant information from the knowledge base:**\n"]
    for i, chunk in enumerate(chunks[:config.LLM_FALLBACK_CHUNKS], 1):
        src = chunk.get("source", "knowledge base")
        pg = chunk.get("page", "?")
        sim = chunk.get("similarity", 0)
        text = chunk["text"]

        # Truncate long chunks for readability
        if len(text) > config.LLM_FALLBACK_CHARS:
            text = text[:config.LLM_FALLBACK_CHARS] + "..."

        lines.append(f"**[Source {i}: {src}, Page {pg}]** (relevance: {sim:.0%})")
        lines.append(text)
        lines.append("")

    lines.append(f"_Source library last verified: {config.POLICY_LAST_VERIFIED_DATE}_")
    return "\n".join(lines)


def extract_cited_pages(answer: str) -> list[int]:
    pattern = r"\[Page (\d+)\]"
    matches = re.findall(pattern, answer)
    return list(set(int(m) for m in matches))


def get_answer(
    query: str,
    chat_history: list = None,
    threshold: float = None,
) -> dict:
    """
    Main RAG pipeline:
    1. Retrieve relevant chunks from ChromaDB
    2. Try Groq LLM for a grounded answer
    3. Fall back to raw chunk display if Groq unavailable
    """
    if chat_history is None:
        chat_history = []

    # Retry initialization so a long-running Streamlit process can pick up a
    # newly installed optional client without requiring a full service restart.
    if not _groq_available:
        _init_groq()

    # Step 1: Retrieve
    chunks, is_answerable, actual_k = retrieve_and_filter(query, threshold=threshold)

    if not chunks:
        return {
            "answer": "No relevant information found in the knowledge base.",
            "chunks": [],
            "is_answerable": False,
            "pages_cited": [],
            "confidence": {"score": 0.0, "label": "none"},
            "actual_k": actual_k,
            "llm_used": False,
        }

    context = format_context(chunks)
    confidence = get_confidence_label(chunks)

    # Step 2: Try Groq LLM
    if _groq_client and _groq_available:
        try:
            user_message = (
                f"Context from knowledge base:\n{context}\n\n"
                f"Question: {query}\n\n"
                "Answer only from the context. Cite each factual claim as [Page X] or [Source: filename]."
            )
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ]
            response = _groq_client.chat.completions.create(
                model=config.GROQ_MODEL,
                messages=messages,
                max_tokens=config.MAX_TOKENS,
                temperature=config.TEMPERATURE,
                timeout=config.LLM_TIMEOUT,
            )
            answer = response.choices[0].message.content.strip()
            pages_cited = extract_cited_pages(answer)
            validation = validate_citations(answer, chunks)
            if not validation["is_valid"]:
                raise ValueError(validation["message"])
            if validation["is_refusal"]:
                raise ValueError("The model refused despite qualifying retrieved evidence")
            return {
                "answer": answer,
                "chunks": chunks,
                "is_answerable": True,
                "pages_cited": pages_cited,
                "confidence": confidence,
                "actual_k": actual_k,
                "llm_used": True,
            }
        except Exception as e:
            # Groq failed — fall through to raw retrieval display
            pass

    # Step 3: Fallback — format raw chunks as structured evidence
    answer = _format_fallback_answer(chunks, query)
    return {
        "answer": answer,
        "chunks": chunks,
        "is_answerable": True,
        "pages_cited": [c.get("page", 0) for c in chunks[:config.LLM_FALLBACK_CHUNKS]],
        "confidence": confidence,
        "actual_k": actual_k,
        "llm_used": False,
    }


if __name__ == "__main__":
    print("Testing MerchantOS LLM Agent (with Groq fallback)...")
    print(f"Groq available: {_groq_available}")
    result = get_answer("Is GST mandatory for unregistered sole proprietor under RBI PA Directions 2025?")
    print(f"Is answerable: {result['is_answerable']}")
    print(f"LLM used: {result['llm_used']}")
    print(f"Confidence: {result['confidence']}")
    print(f"Answer preview:\n{result['answer'][:400]}")
