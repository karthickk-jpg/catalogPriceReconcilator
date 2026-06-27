import logging
import sys
import re
from pathlib import Path

# Setup logging
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "app.log"

logger = logging.getLogger("cprp")
logger.setLevel(logging.INFO)

# Avoid adding duplicate handlers if helper is imported multiple times
if not logger.handlers:
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s [%(name)s:%(filename)s:%(lineno)d] - %(message)s"
    )

    # Console Handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File Handler
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(formatter)
    logger.addHandler(fh)


def get_logger(name: str) -> logging.Logger:
    """Returns a child logger of the main application logger."""
    return logging.getLogger(f"cprp.{name}")


def normalize_sku(sku: str) -> str:
    """Normalizes an SKU code by trimming whitespace, stripping common symbols, 
    and converting to uppercase to ensure high match fidelity.
    """
    if sku is None:
        return ""
    # Convert to string, strip whitespace, and upper case
    normalized = str(sku).strip().upper()
    # Remove leading and trailing spaces/hyphens/underscores if they skew comparison
    normalized = re.sub(r"^[\s\-_]+|[\s\-_]+$", "", normalized)
    return normalized


def format_currency(val: float) -> str:
    """Formats numeric price differences as standard currency strings (INR symbol)."""
    if val is None or val != val:  # Handle None/NaN
        return "-"
    return f"₹{val:,.2f}"


def format_percent(val: float) -> str:
    """Formats decimal values to clean percentage format."""
    if val is None or val != val:
        return "-"
    return f"{val:+.2f}%" if val != 0 else "0.00%"
