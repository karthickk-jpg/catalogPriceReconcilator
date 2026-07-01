import logging
import re
import sys
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "app.log"

logger = logging.getLogger("cprp")
logger.setLevel(logging.INFO)

if not logger.handlers:
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s [%(name)s:%(filename)s:%(lineno)d] - %(message)s"
    )

    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(formatter)
    logger.addHandler(fh)


def get_logger(name: str) -> logging.Logger:
    """Returns a child logger of the main application logger."""
    return logging.getLogger(f"cprp.{name}")


def normalize_sku(sku: str) -> str:
    """Normalizes an SKU code for consistent matching."""
    if sku is None:
        return ""
    normalized = str(sku).strip().upper()
    normalized = re.sub(r"^[\s\-_]+|[\s\-_]+$", "", normalized)
    return normalized
