import pytest

from app.gemini_service import _reset_cache_for_tests


@pytest.fixture(autouse=True)
def _clear_analysis_cache():
    """The Gemini analysis cache (gemini_service.py) is module-level, in-memory state
    shared by the whole test process. Without this, one test's cached analysis for a
    given note text leaks into any other test that happens to reuse the same text
    (e.g. the repeated "Patient has a cold." fixture across test_notes_router.py),
    silently skipping the mocked Gemini call it expected to hit."""
    _reset_cache_for_tests()
    yield
    _reset_cache_for_tests()
