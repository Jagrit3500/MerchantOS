import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymupdf
from pathlib import Path
from src import config


def parse_pdf(pdf_path: str) -> list[dict]:
    """
    Parse PDF and extract page-wise text chunks with metadata.
    Returns list of chunk dictionaries.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = pymupdf.open(pdf_path)
    chunks = []
    chunk_id = 0

    for page_num in range(len(doc)):
        page = doc[page_num]

        # Better text cleaning — removes extra whitespace
        text = " ".join(page.get_text().split())

        if not text:
            continue

        page_chunks = create_chunks(
            text=text,
            page_num=page_num + 1,  # 1-indexed
            source=Path(pdf_path).name,
            chunk_id_start=chunk_id
        )

        chunks.extend(page_chunks)
        chunk_id += len(page_chunks)

    doc.close()
    return chunks


def create_chunks(
    text: str,
    page_num: int,
    source: str,
    chunk_id_start: int,
) -> list[dict]:
    """
    Split text into overlapping chunks with metadata.
    """
    # Guard against infinite loop
    if config.CHUNK_OVERLAP >= config.CHUNK_SIZE:
        raise ValueError(
            f"CHUNK_OVERLAP ({config.CHUNK_OVERLAP}) must be "
            f"smaller than CHUNK_SIZE ({config.CHUNK_SIZE})"
        )

    chunks = []
    start = 0
    local_id = 0

    while start < len(text):
        end = start + config.CHUNK_SIZE
        chunk_text = text[start:end]

        if chunk_text.strip():
            chunks.append({
                "chunk_id": f"{Path(source).stem[:config.INGEST_SOURCE_ID_MAX_LENGTH]}_page_{page_num}_chunk_{chunk_id_start + local_id}",
                "text": chunk_text.strip(),
                "page": page_num,
                "page_start": page_num,
                "page_end": page_num,
                "source": source,
                "char_start": start,
                "char_end": end
            })
            local_id += 1

        # Move forward by chunk_size minus overlap
        start = end - config.CHUNK_OVERLAP

        # Safety guard — prevent infinite loop
        if end >= len(text):
            break

    return chunks


def save_uploaded_pdf(uploaded_file) -> str:
    """
    Save Streamlit uploaded file to uploads folder.
    Returns the saved file path.
    """
    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    safe_name = os.path.basename(uploaded_file.name)
    file_path = os.path.join(config.UPLOAD_DIR, safe_name)

    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return file_path


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        chunks = parse_pdf(pdf_path)
        print(f"Total chunks: {len(chunks)}")
        print(f"\nFirst chunk preview:")
        print(chunks[0])
        print(f"\nLast chunk preview:")
        print(chunks[-1])
    else:
        print("Usage: python src/pdf_parser.py <path_to_pdf>")
