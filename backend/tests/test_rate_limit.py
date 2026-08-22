import pytest
from fastapi import HTTPException

from app.rate_limit import _reset_for_tests, enforce_note_submission_rate_limit


@pytest.fixture(autouse=True)
def _reset():
    _reset_for_tests()
    yield
    _reset_for_tests()


def test_allows_up_to_the_limit():
    for _ in range(5):
        enforce_note_submission_rate_limit("uid-a")  # should not raise


def test_blocks_the_next_one_over_the_limit():
    for _ in range(5):
        enforce_note_submission_rate_limit("uid-a")
    with pytest.raises(HTTPException) as exc_info:
        enforce_note_submission_rate_limit("uid-a")
    assert exc_info.value.status_code == 429


def test_limit_is_per_user_not_global():
    for _ in range(5):
        enforce_note_submission_rate_limit("uid-a")
    enforce_note_submission_rate_limit("uid-b")  # different user, should not raise
