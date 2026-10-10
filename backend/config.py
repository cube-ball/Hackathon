"""Settings. Real environment variables win; backend/.env fills in anything missing.

Never commit backend/.env (it is in .gitignore). Copy backend/.env.example instead.
"""
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent


def _load_dotenv(path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


_load_dotenv(BACKEND_DIR / ".env")


def get(name, default=None):
    value = os.environ.get(name, "").strip()
    return value or default


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = get("OPENROUTER_MODEL", "apodex/apodex-1.1-mini:free")
DB_PATH = Path(get("STUDYFLOW_DB", str(BACKEND_DIR / "studyflow.db")))
USER_ID = get("STUDYFLOW_USER_ID", "local-student")   # one synthetic student for the demo
APP_URL = get("APP_URL", "http://localhost:8501")      # where Stripe sends people back to
FREE_UPDATES = int(get("FREE_UPDATES", "3"))
PRICE_CENTS = 900                                      # Semester Pass, EUR 9.00
CURRENCY = "eur"
PRODUCT_NAME = "Semester Pass"


def openrouter_key():
    return get("OPENROUTER_API_KEY")


def stripe_secret_key():
    return get("STRIPE_SECRET_KEY")


def stripe_webhook_secret():
    return get("STRIPE_WEBHOOK_SECRET")
