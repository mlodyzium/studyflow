"""Request-local message translation. English source strings are catalog keys."""
import json
import re
from contextvars import ContextVar
from pathlib import Path

language: ContextVar[str] = ContextVar("language", default="en")
_catalog_path = Path(__file__).with_name("locales") / "pl.json"
_polish = json.loads(_catalog_path.read_text(encoding="utf-8")) if _catalog_path.exists() else {}


def tr(message: str, *values: object) -> str:
    template = _polish.get(message, message) if language.get() == "pl" else message
    return re.sub(r"\{(\d+)\}", lambda match: str(values[int(match[1])]) if int(match[1]) < len(values) else match[0], template)


async def localize_request(request, call_next):
    preferred = request.headers.get("accept-language", "en").split(",")[0].split(";")[0].strip().lower()
    selected = "pl" if preferred.startswith("pl") else "en"
    token = language.set(selected)
    try:
        response = await call_next(request)
        response.headers["Content-Language"] = selected
        existing = response.headers.get("Vary", "")
        response.headers["Vary"] = ", ".join(filter(None, (existing, "Accept-Language")))
        return response
    finally:
        language.reset(token)
