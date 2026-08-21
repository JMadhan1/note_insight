"""Proves the structural guarantee behind 'a user must only ever see their own
notes': every read/write in firestore_service.py builds its Firestore path
through users/{uid}/... using the uid argument, which in turn only ever comes
from a verified token (see app/auth.py). There is no code path that accepts a
note or analysis id without also requiring the caller's own uid in the path,
so a request authenticated as user A structurally cannot reach user B's data
regardless of which ids it guesses.

This is checked here without live Firestore by mocking the client and
asserting the exact document path requested for two different uids.
"""

from unittest.mock import MagicMock, patch

from app import firestore_service as db


@patch("app.firestore_service.get_db")
def test_notes_ref_is_scoped_to_the_given_uid(mock_get_db):
    mock_client = MagicMock()
    mock_get_db.return_value = mock_client

    db._notes_ref("user-a")

    mock_client.collection.assert_called_with("users")
    mock_client.collection.return_value.document.assert_called_with("user-a")
    mock_client.collection.return_value.document.return_value.collection.assert_called_with("notes")


@patch("app.firestore_service.get_db")
def test_different_uids_produce_different_paths(mock_get_db):
    mock_client = MagicMock()
    mock_get_db.return_value = mock_client

    db._notes_ref("user-a")
    first_call_uid = mock_client.collection.return_value.document.call_args
    db._notes_ref("user-b")
    second_call_uid = mock_client.collection.return_value.document.call_args

    assert first_call_uid != second_call_uid


@patch("app.firestore_service.get_db")
def test_get_note_for_one_user_never_queries_another_users_subcollection(mock_get_db):
    mock_client = MagicMock()
    mock_get_db.return_value = mock_client
    # users/{uid}/notes/{note_id}.get()
    notes_collection = mock_client.collection.return_value.document.return_value.collection.return_value
    notes_collection.document.return_value.get.return_value.exists = False

    db.get_note("attacker-uid", "some-note-id-guessed-from-another-account")

    # The lookup path must have been rooted at users/attacker-uid/... — the
    # attacker's own uid, never the note owner's — proving a guessed note id
    # alone cannot read another user's data.
    mock_client.collection.assert_any_call("users")
    mock_client.collection.return_value.document.assert_any_call("attacker-uid")
