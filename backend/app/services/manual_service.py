from functools import lru_cache
from pathlib import Path

_MANUAL_PATH = Path(__file__).resolve().parent.parent / "content" / "manual.html"


@lru_cache
def get_manual_html() -> str:
    return _MANUAL_PATH.read_text(encoding="utf-8")
