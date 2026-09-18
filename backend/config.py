import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / "backend" / ".env")
RUNTIME = ROOT / ".runtime"
RUNTIME.mkdir(exist_ok=True)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(RUNTIME / 'onda.db').as_posix()}")
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")
BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEV_MODE = os.getenv("ONDA_DEV_MODE", "false").lower() == "true"
MODEL_TIMEOUT = 75
PROMPT_VERSION = "onda-2026-09-18-v1"
