import pytest

from app.core.i18n import language


@pytest.fixture(autouse=True)
def legacy_polish_regression_language():
    """Existing regression fixtures describe Polish requests and responses."""
    token = language.set("pl")
    try:
        yield
    finally:
        language.reset(token)
