from app.gemini_service import verify_quote


def test_exact_match():
    assert verify_quote("patient has diabetes", "The patient has diabetes and hypertension.")


def test_case_and_whitespace_insensitive():
    assert verify_quote("Patient   HAS diabetes", "the patient has diabetes.")


def test_punctuation_tolerant():
    assert verify_quote("diabetes uncontrolled", "Diagnosis: diabetes, uncontrolled since 2019.")


def test_fabricated_quote_rejected():
    assert not verify_quote("patient denies chest pain", "The patient reports occasional chest pain.")


def test_empty_quote_rejected():
    assert not verify_quote("", "Some note text.")


def test_whitespace_only_quote_rejected():
    assert not verify_quote("   ", "Some note text.")


def test_similar_but_different_word_not_falsely_accepted():
    # "diabetic" must not satisfy a claimed quote of "diabetes"
    assert not verify_quote("diabetes", "The patient is diabetic and hypertensive.")
