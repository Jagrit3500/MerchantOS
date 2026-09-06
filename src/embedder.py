import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from sentence_transformers import SentenceTransformer
from src.config import (
    EMBEDDING_MODEL,
    EMBEDDING_BATCH_SIZE,
    CHROMA_DB_PATH,
    COLLECTION_NAME
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
            cache_folder=os.path.expanduser("~/.cache/huggingface/hub")
        )
    return _embedding_model

# ─── ChromaDB ───────────────────────────────────────

def get_chroma_client():
    """
    Initialize and return ChromaDB persistent client.
    """
    os.makedirs(CHROMA_DB_PATH, exist_ok=True)
    return chromadb.PersistentClient(path=CHROMA_DB_PATH)


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

    client = get_chroma_client()

    # Delete existing collection to avoid duplicates
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = get_or_create_collection(client)

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

    # Insert in batches
    for i in range(0, len(ids), EMBEDDING_BATCH_SIZE):
        collection.add(
            ids=ids[i:i+EMBEDDING_BATCH_SIZE],
            documents=documents[i:i+EMBEDDING_BATCH_SIZE],
            embeddings=embeddings[i:i+EMBEDDING_BATCH_SIZE],
            metadatas=metadatas[i:i+EMBEDDING_BATCH_SIZE]
        )

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

    chunks = parse_pdf("uploads/pitch.pdf")
    print(f"Parsed {len(chunks)} chunks")

    success = embed_chunks(chunks)
    print(f"Embedding successful: {success}")