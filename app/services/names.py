import re


ACRONYMS = {"ai", "api", "css", "html", "http", "https", "js", "json", "php", "sql", "ui", "ux", "xml"}


def normalize_name(value: str) -> str:
    """Capitalize a user-facing name while preserving common technical acronyms."""
    words = re.split(r"(\s+|[-/])", value.strip())
    result = []
    first_word = True
    for word in words:
        if not word or word.isspace() or word in {"-", "/"}:
            result.append(word)
        elif word.casefold() in ACRONYMS:
            result.append(word.upper())
            first_word = False
        elif first_word:
            result.append(word[:1].upper() + word[1:])
            first_word = False
        else:
            result.append(word)
    return "".join(result)
