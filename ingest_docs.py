"""
Ingest RBI + Razorpay documents into ChromaDB for Agent 1.
Handles both .pdf and .txt files in the /docs folder.
Uses source-prefixed chunk IDs to prevent duplicates across multiple docs.
Run once before starting the app: python ingest_docs.py
"""
import sys, os
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.pdf_parser import parse_pdf
from src.embedder import embed_chunks
from src import config


def parse_txt(file_path: str) -> list[dict]:
    """
    Parse a plain text file into chunks.
    Uses source-prefixed chunk IDs to avoid collisions across multiple docs.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        full_text = " ".join(f.read().split())

    source = os.path.basename(file_path)
    # Sanitize source for use in ID (alphanumeric + underscore, max 20 chars)
    source_prefix = "".join(c if c.isalnum() else "_" for c in source.split(".")[0])[:config.INGEST_SOURCE_ID_MAX_LENGTH]

    chunks = []
    start = 0
    chunk_id = 0
    page_num = 1

    while start < len(full_text):
        end = start + config.CHUNK_SIZE
        chunk_text = full_text[start:end].strip()
        if chunk_text:
            chunks.append({
                "chunk_id": f"{source_prefix}_p{page_num}_c{chunk_id}",
                "text": chunk_text,
                "page": page_num,
                "page_start": page_num,
                "page_end": page_num,
                "source": source,
                "char_start": start,
                "char_end": end,
            })
            chunk_id += 1
            if chunk_id % config.TXT_CHUNKS_PER_PAGE == 0:
                page_num += 1

        if end >= len(full_text):
            break
        start = end - config.CHUNK_OVERLAP

    return chunks


def ingest_all():
    print("=" * 60)
    print("MerchantOS - Document Ingestion")
    print("=" * 60)

    if config.CHUNK_OVERLAP >= config.CHUNK_SIZE:
        raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
    if config.TXT_CHUNKS_PER_PAGE < 1:
        raise ValueError("TXT_CHUNKS_PER_PAGE must be at least 1")

    if not os.path.isdir(config.DOCS_DIR):
        print(f"ERROR: Document directory does not exist: {config.DOCS_DIR}")
        return False
    files = os.listdir(config.DOCS_DIR)
    pdfs = sorted([f for f in files if f.endswith(".pdf")])
    txts = sorted([f for f in files if f.endswith(".txt")])
    all_docs = pdfs + txts

    if not all_docs:
        print("ERROR: No documents found in /docs folder!")
        return False

    print(f"Found {len(pdfs)} PDF(s) and {len(txts)} TXT file(s)")
    all_chunks = []

    for doc in pdfs:
        path = os.path.join(config.DOCS_DIR, doc)
        print(f"\n[PDF] Processing: {doc}")
        try:
            chunks = parse_pdf(path)
            print(f"      Parsed: {len(chunks)} chunks")
            all_chunks.extend(chunks)
        except Exception as e:
            print(f"      ERROR: {e}")

    for doc in txts:
        path = os.path.join(config.DOCS_DIR, doc)
        print(f"\n[TXT] Processing: {doc}")
        try:
            chunks = parse_txt(path)
            prefix = chunks[0]["chunk_id"][:25] if chunks else "none"
            print(f"      Parsed: {len(chunks)} chunks | ID prefix: {prefix}...")
            all_chunks.extend(chunks)
        except Exception as e:
            print(f"      ERROR: {e}")

    if not all_chunks:
        print("No chunks to embed!")
        return False

    # Verify all IDs are unique before embedding
    ids = [c["chunk_id"] for c in all_chunks]
    unique_ids = set(ids)
    if len(ids) != len(unique_ids):
        dupes = sorted(chunk_id for chunk_id, count in Counter(ids).items() if count > 1)
        print(f"ERROR: Duplicate chunk IDs found: {dupes}")
        return False

    print(f"\nTotal chunks: {len(all_chunks)} | Unique IDs: {len(unique_ids)} | ID check: OK")
    print("Embedding into ChromaDB...")
    success = embed_chunks(all_chunks)

    if success:
        print("\nIngestion complete!")
        print("Sources indexed:")
        sources = sorted(set(c["source"] for c in all_chunks))
        for s in sources:
            count = sum(1 for c in all_chunks if c["source"] == s)
            print(f"  - {s}: {count} chunks")
        print("\nRun: python launch.py (or streamlit run home.py)")
    else:
        print("\nEmbedding failed.")
    return success


if __name__ == "__main__":
    ingest_all()
