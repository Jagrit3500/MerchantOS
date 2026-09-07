import os
from dotenv import load_dotenv

# Always load .env from the project root (MerchantOS folder), not cwd
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")
load_dotenv(ENV_PATH, override=True)

# Force offline mode for HuggingFace
os.environ["TRANSFORMERS_OFFLINE"] = os.getenv("TRANSFORMERS_OFFLINE", "1")
os.environ["HF_DATASETS_OFFLINE"]  = os.getenv("HF_DATASETS_OFFLINE", "1")

# Networking & Service Ports
HOST = os.getenv("MERCHANTOS_HOST", "localhost")
PORT_HOME = int(os.getenv("PORT_HOME", "8501"))
PORT_AGENT1 = int(os.getenv("PORT_AGENT1", "8502"))
PORT_AGENT2 = int(os.getenv("PORT_AGENT2", "8503"))
PORT_AGENT3 = int(os.getenv("PORT_AGENT3", "8504"))

# Workspace & Entity Metadata
WORKSPACE_NAME = os.getenv("MERCHANT_WORKSPACE_NAME", "Merchant workspace")
CURRENCY = os.getenv("MERCHANT_CURRENCY", "INR")
AGGREGATOR_NAME = os.getenv("PAYMENT_AGGREGATOR_NAME", "Razorpay Software Private Limited")
AGGREGATOR_SHORT = os.getenv("PAYMENT_AGGREGATOR_SHORT", "Razorpay")
AGGREGATOR_GRIEVANCE_EMAIL = os.getenv("PAYMENT_AGGREGATOR_GRIEVANCE_EMAIL", "grievance.officer@razorpay.com")

# Dynamic Fee & Tax Settings
MDR_RATE_UPI = float(os.getenv("MDR_RATE_UPI", "0.0"))
MDR_RATE_CARD = float(os.getenv("MDR_RATE_CARD", "2.0"))
MDR_RATE_NETBANKING = float(os.getenv("MDR_RATE_NETBANKING", "2.0"))
MDR_RATE_WALLET = float(os.getenv("MDR_RATE_WALLET", "2.0"))
MDR_RATE_EMI = float(os.getenv("MDR_RATE_EMI", "2.5"))
MDR_RATE_PAYLATER = float(os.getenv("MDR_RATE_PAYLATER", "2.5"))
MDR_RATE_DEFAULT = float(os.getenv("MDR_RATE_DEFAULT", "2.0"))
GST_RATE = float(os.getenv("GST_RATE", "18.0"))

# API Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# LLM Settings
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
MAX_TOKENS   = int(os.getenv("MAX_TOKENS", "1024"))
TEMPERATURE  = float(os.getenv("TEMPERATURE", "0.0"))

# Embedding Settings
EMBEDDING_MODEL      = os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "50"))

# Chunking Settings
CHUNK_SIZE    = int(os.getenv("CHUNK_SIZE", "900"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))

# ChromaDB - ABSOLUTE PATH so it works from any working directory
_chroma_relative = os.getenv("CHROMA_DB_PATH", "chroma_db")
CHROMA_DB_PATH = (
    _chroma_relative
    if os.path.isabs(_chroma_relative)
    else os.path.join(PROJECT_ROOT, _chroma_relative)
)
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "pdf_chunks")

# Retrieval Settings
TOP_K_RESULTS        = int(os.getenv("TOP_K_RESULTS", "5"))
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.55"))

# File Settings
_upload_relative = os.getenv("UPLOAD_DIR", "uploads")
UPLOAD_DIR = (
    _upload_relative
    if os.path.isabs(_upload_relative)
    else os.path.join(PROJECT_ROOT, _upload_relative)
)


def validate_groq_key():
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not found in .env file!")


if __name__ == "__main__":
    print("MerchantOS Config Check:")
    print(f"  PROJECT_ROOT:    {PROJECT_ROOT}")
    print(f"  ENV_PATH:        {ENV_PATH} | exists={os.path.exists(ENV_PATH)}")
    print(f"  CHROMA_DB_PATH:  {CHROMA_DB_PATH} | exists={os.path.exists(CHROMA_DB_PATH)}")
    print(f"  HOST & PORTS:    {HOST} -> Home:{PORT_HOME}, A1:{PORT_AGENT1}, A2:{PORT_AGENT2}, A3:{PORT_AGENT3}")
    print(f"  AGGREGATOR:      {AGGREGATOR_NAME} ({AGGREGATOR_SHORT})")
    print(f"  WORKSPACE:       {WORKSPACE_NAME} [{CURRENCY}]")
