import logging
import sys
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

_FMT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str, level: int = logging.DEBUG) -> logging.Logger:
    logger = logging.getLogger(name)

    if logger.handlers:          
        return logger

    logger.setLevel(level)

    
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(_FMT, _DATE))
    logger.addHandler(ch)

    
    fh = logging.FileHandler(LOG_DIR / "assistant.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(_FMT, _DATE))
    logger.addHandler(fh)

    logger.propagate = False
    return logger