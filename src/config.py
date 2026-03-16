from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_PDF_DIR = PROJECT_ROOT / "raw_documents" / "pdf"
OUTPUT_JSON_DIR = PROJECT_ROOT / "output" / "json"
OUTPUT_GRAPH_DIR = PROJECT_ROOT / "output" / "graphs"

OUTPUT_JSON_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_GRAPH_DIR.mkdir(parents=True, exist_ok=True)

# OCR fallback threshold: pages with fewer chars than this trigger OCR
OCR_CHAR_THRESHOLD = 50

# LLM config (scaffold for v2)
LLM_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4")
