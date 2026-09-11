import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from sentence_transformers import SentenceTransformer
from src.config import (
    EMBEDDING_MODEL,
    EMBEDDING_BATCH_SIZE,
    CHROMA_DB_PATH,
    COLLECTION_NAME,
    EMBEDDING_CACHE_DIR,
    UPLOAD_DIR,
)

# ─── Lazy model loader ───────────────────────────────
_embedding_model = None


def get_embedding_model():
    """
    Load model from local cache only.
    TRANSFORMERS_OFFLINE=1 prevents any network calls.
    """
    global _embedding_model
    if _embedding_model is None:
        # Force local cache only
        _embedding_model = SentenceTransformer(
            EMBEDDING_MODEL,
            cache_folder=EMBEDDING_CACHE_DIR
        )
    return _embedding_model

# ─── ChromaDB ───────────────────────────────────────

def get_chroma_client():
    """
    Initialize and return ChromaDB persistent client.
    """
    os.makedirs(CHROMA_DB_PATH, exist_ok=True)
    return chromadb.PersistentClient(path=CHROMA_DB_PATH)


def reconnect_chroma_client():
    """Reconnect to the persistent index so external rebuilds become visible."""
    from chromadb.api.shared_system_client import SharedSystemClient

    current = get_chroma_client()
    system = getattr(current, "_system", None)
    if system is not None:
        system.stop()
    SharedSystemClient.clear_system_cache()
    return get_chroma_client()


def get_or_create_collection(client):
    """
    Get existing collection or create new one with cosine space.
    """
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )


# ─── Embedding ──────────────────────────────────────

def embed_chunks(chunks: list[dict]) -> bool:
    """
    Embed chunks and store in ChromaDB.
    Deletes existing collection to avoid duplicates on re-upload.
    Returns True if successful.
    """
    if not chunks:
        return False

    ids = []
    documents = []
    metadatas = []

    for chunk in chunks:
        ids.append(chunk["chunk_id"])
        documents.append(chunk["text"])
        metadatas.append({
            "page": chunk["page"],
            "page_start": chunk["page_start"],
            "page_end": chunk["page_end"],
            "source": chunk["source"],
            "char_start": chunk["char_start"],
            "char_end": chunk["char_end"]
        })

    print(f"Generating embeddings for {len(chunks)} chunks...")

    embeddings = get_embedding_model().encode(
        documents,
        normalize_embeddings=True
    ).tolist()

    # Upsert first so a failed ingestion never begins by deleting the usable index.
    client = get_chroma_client()
    collection = get_or_create_collection(client)
    existing_ids = set(collection.get()["ids"])

    # Insert in batches
    for i in range(0, len(ids), EMBEDDING_BATCH_SIZE):
        collection.upsert(
            ids=ids[i:i+EMBEDDING_BATCH_SIZE],
            documents=documents[i:i+EMBEDDING_BATCH_SIZE],
            embeddings=embeddings[i:i+EMBEDDING_BATCH_SIZE],
            metadatas=metadatas[i:i+EMBEDDING_BATCH_SIZE]
        )

    stale_ids = sorted(existing_ids.difference(ids))
    if stale_ids:
        collection.delete(ids=stale_ids)

    print(f"Successfully embedded {len(chunks)} chunks!")
    return True


def get_embedding(text: str) -> list[float]:
    """
    Get normalized embedding for a single query text.
    """
    return get_embedding_model().encode(
        text,
        normalize_embeddings=True
    ).tolist()


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.pdf_parser import parse_pdf

    test_pdf = sys.argv[1] if len(sys.argv) > 1 else os.path.join(UPLOAD_DIR, "pitch.pdf")
    if os.path.exists(test_pdf):
        chunks = parse_pdf(test_pdf)
        print(f"Parsed {len(chunks)} chunks")
        success = embed_chunks(chunks)
        print(f"Embedding successful: {success}")
    else:
        print("ChromaDB client test: OK")
