import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
TEMP_DIR = Path("/tmp")

# Ensure data dir exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

# API Keys
HF_TOKEN = os.getenv("HF_TOKEN")
if not HF_TOKEN:
    # Try loading from local huggingface token file
    token_path = Path.home() / ".huggingface" / "token"
    if token_path.exists():
        HF_TOKEN = token_path.read_text().strip()

# DashScope API Key (for TTS)
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY") or os.getenv("API_KEY")

# Service Configuration
LLM_MODEL_REPO = "Qwen/Qwen2.5-72B-Instruct"
# TTS_SPACE_REPO = "Qwen/Qwen3-TTS-Voice-Design" # Deprecated in favor of DashScope API

# Server
PORT = int(os.getenv("PORT", 8000))
HOST = "0.0.0.0"
