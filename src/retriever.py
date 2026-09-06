import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.embedder import get_chroma_client, get_embedding, get_or_create_collection
from src.config import TOP_K_RESULTS, SIMILARITY_THRESHOLD


def get_dynamic_k(total_chunks: int) -> int:
    """
    Dynamically calculate k based on total chunks in DB.
    More chunks = wider search net needed.
    """
    if total_chunks <= 40:
        return 5
    elif total_chunks <= 150:
        return 8
    elif total_chunks <= 450:
        return 15
    else:
        return 20


def retrieve_chunks(query: str, k: int = TOP_K_RESULTS) -> tuple[list[dict], int]:
    """
    Retrieve top-k most relevant chunks for a query.
    Uses dynamic k based on collection size.
    Returns (chunks, actual_k_used)
    """
    client = get_chroma_client()
    collection = get_or_create_collection(client)

    total_chunks = collection.count()

    # Edge case — empty DB
    if total_chunks == 0:
        return [], 0

    # Use dynamic k, bounded by total chunks
    dynamic_k = get_dynamic_k(total_chunks)
    actual_k = min(dynamic_k, total_chunks)

    query_embedding = get_embedding(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=actual_k,
        include=["documents", "metadatas", "distances"]
    )

    if not results["documents"][0]:
        return [], actual_k

    chunks = []
    for i in range(len(results["documents"][0])):
        distance = results["distances"][0][i]
        similarity = 1 - (distance / 2)

        chunks.append({
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "similarity": round(similarity, 4),
            "page": results["metadatas"][0][i]["page"],
            "source": results["metadatas"][0][i]["source"],
            # Store debug info in each chunk
            "k_used": actual_k,
            "total_chunks": total_chunks
        })

    chunks.sort(key=lambda x: x["similarity"], reverse=True)
    return chunks, actual_k


def filter_by_threshold(
    chunks: list[dict],
    threshold: float | None = None
) -> list[dict]:
    """
    Filter chunks below similarity threshold.
    Uses provided threshold or falls back to config.
    """
    active_threshold = threshold if threshold is not None else SIMILARITY_THRESHOLD
    return [c for c in chunks if c["similarity"] >= active_threshold]


def retrieve_and_filter(
    query: str,
    threshold: float | None = None
) -> tuple[list[dict], bool, int]:
    """
    Full retrieval pipeline with evidence filtering.
    Returns (chunks, is_answerable, actual_k_used)
    """
    chunks, actual_k = retrieve_chunks(query)

    if not chunks:
        return [], False, actual_k

    filtered_chunks = filter_by_threshold(chunks, threshold=threshold)
    is_answerable = len(filtered_chunks) > 0

    return filtered_chunks, is_answerable, actual_k


def format_context(chunks: list[dict]) -> str:
    """
    Format retrieved chunks into context string for LLM.
    """
    context_parts = []
    for chunk in chunks:
        context_parts.append(f"[Page {chunk['page']}]\n{chunk['text']}")
    return "\n\n---\n\n".join(context_parts)


if __name__ == "__main__":
    query = "What is this document about?"
    print(f"Query: {query}\n")

    chunks, is_answerable, actual_k = retrieve_and_filter(query)
    print(f"Is answerable: {is_answerable}")
    print(f"Dynamic K used: {actual_k}")
    print(f"Chunks retrieved: {len(chunks)}")

    if chunks:
        print(f"\nTop chunk (similarity: {chunks[0]['similarity']}):")
        print(f"Page: {chunks[0]['page']}")
        print(f"Text preview: {chunks[0]['text'][:200]}")