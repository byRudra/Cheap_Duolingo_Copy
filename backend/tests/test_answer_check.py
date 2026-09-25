"""normalize() and server-side answer checking (§5)."""

import pytest

from app.errors import AppError
from app.models import ExerciseType
from app.services.answer_check import check_answer, match_text, normalize, strip_accents

MC = ExerciseType.MULTIPLE_CHOICE
FB = ExerciseType.FILL_BLANK
WB = ExerciseType.WORD_BANK
TA = ExerciseType.TYPE_ANSWER
MP = ExerciseType.MATCH_PAIRS

GREETING = {"accepted": ["Buenos días", "Buen día"]}


# ── normalize ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("HOLA", "hola"),  # case
        ("  hola  ", "hola"),  # trim
        ("buenos    días", "buenos días"),  # collapse spaces
        ("buenos\t\n días", "buenos días"),  # collapse any whitespace
        ("¡Hola!", "hola"),  # inverted + regular exclamation
        ("¿Cómo estás?", "cómo estás"),  # inverted + regular question
        ("Sí, gracias.", "sí gracias"),  # comma + period
        ("Hola , amigo", "hola amigo"),  # stripped punctuation doesn't leave double spaces
        ("  ¡¿  Qué   TAL?!  ", "qué tal"),
        ("", ""),
    ],
)
def test_normalize(raw, expected):
    assert normalize(raw) == expected


def test_normalize_keeps_accents_and_other_characters():
    assert normalize("Adiós") == "adiós"
    assert normalize("ÑANDÚ") == "ñandú"
    assert normalize("I'm") == "i'm"  # apostrophes are not in the strip set


def test_strip_accents():
    assert strip_accents("adiós señor, qué tal") == "adios senor, que tal"


# ── multiple choice / fill in the blank ──────────────────────────────────────


@pytest.mark.parametrize("kind", [MC, FB])
def test_choice_exact_and_case_insensitive(kind):
    solution = {"answer": "Hola"}
    assert check_answer(kind, solution, {"answer": "Hola"}).correct
    assert check_answer(kind, solution, {"answer": "  hola "}).correct
    result = check_answer(kind, solution, {"answer": "Adiós"})
    assert not result.correct
    assert result.correct_answer == "Hola"
    assert result.note is None


def test_choice_is_not_accent_tolerant():
    # Accent forgiveness applies only to TYPE_ANSWER and WORD_BANK.
    assert not check_answer(MC, {"answer": "Adiós"}, {"answer": "Adios"}).correct


# ── type answer ──────────────────────────────────────────────────────────────


def test_type_answer_exact_match_has_no_note():
    result = check_answer(TA, GREETING, {"text": "Buenos días"})
    assert result.correct
    assert result.correct_answer == "Buenos días"
    assert result.note is None


def test_type_answer_ignores_case_whitespace_and_punctuation():
    result = check_answer(TA, GREETING, {"text": "  ¡BUENOS    días! "})
    assert result.correct and result.note is None


def test_type_answer_multiple_accepted_answers():
    result = check_answer(TA, GREETING, {"text": "buen día"})
    assert result.correct
    assert result.note is None
    assert result.correct_answer == "Buenos días"  # the primary answer is shown


def test_type_answer_accent_note():
    result = check_answer(TA, GREETING, {"text": "buenos dias"})
    assert result.correct
    assert result.note == "Watch your accents: Buenos días"


def test_type_answer_accent_note_names_the_matched_alternative():
    result = check_answer(TA, GREETING, {"text": "Buen dia"})
    assert result.correct
    assert result.note == "Watch your accents: Buen día"


def test_type_answer_uppercase_accents_are_exact():
    result = check_answer(TA, {"accepted": ["Adiós"]}, {"text": "ADIÓS"})
    assert result.correct and result.note is None


def test_type_answer_wrong():
    result = check_answer(TA, GREETING, {"text": "buenas noches"})
    assert not result.correct
    assert result.correct_answer == "Buenos días"
    assert result.note is None


def test_type_answer_empty_is_wrong_not_an_error():
    assert not check_answer(TA, GREETING, {"text": "   "}).correct


def test_decomposed_unicode_accents_count_as_exact():
    decomposed = "Adiós"  # visually "Adiós"
    result = check_answer(TA, {"accepted": ["Adiós"]}, {"text": decomposed})
    assert result.correct
    assert result.note is None


# ── word bank ────────────────────────────────────────────────────────────────


def test_word_bank_correct_order():
    result = check_answer(WB, GREETING, {"tiles": ["Buenos", "días"]})
    assert result.correct and result.note is None


def test_word_bank_order_matters():
    result = check_answer(WB, GREETING, {"tiles": ["días", "Buenos"]})
    assert not result.correct
    assert result.correct_answer == "Buenos días"


def test_word_bank_extra_or_missing_tiles_are_wrong():
    assert not check_answer(WB, GREETING, {"tiles": ["Buenos"]}).correct
    assert not check_answer(WB, GREETING, {"tiles": ["Buenos", "días", "noches"]}).correct
    assert not check_answer(WB, GREETING, {"tiles": []}).correct


def test_word_bank_alternative_and_accent_note():
    assert check_answer(WB, GREETING, {"tiles": ["Buen", "día"]}).correct
    result = check_answer(WB, GREETING, {"tiles": ["buenos", "dias"]})
    assert result.correct
    assert result.note == "Watch your accents: Buenos días"


def test_word_bank_punctuated_tiles():
    solution = {"accepted": ["¿Cómo estás?"]}
    assert check_answer(WB, solution, {"tiles": ["¿Cómo", "estás?"]}).correct
    assert check_answer(WB, solution, {"tiles": ["Cómo", "estás"]}).correct


# ── match pairs ──────────────────────────────────────────────────────────────


def test_match_pairs_completed():
    result = check_answer(MP, None, {"completed": True})
    assert result.correct
    assert result.correct_answer is None


# ── match_text directly ──────────────────────────────────────────────────────


def test_match_text_without_accent_tolerance():
    result = match_text("adios", ["Adiós"], accent_tolerant=False)
    assert not result.correct


# ── invalid payloads → 422 INVALID_ANSWER ────────────────────────────────────


@pytest.mark.parametrize(
    ("kind", "solution", "payload"),
    [
        (MC, {"answer": "Hola"}, {}),
        (MC, {"answer": "Hola"}, {"answer": 3}),
        (MC, {"answer": "Hola"}, {"text": "Hola"}),
        (FB, {"answer": "bien"}, {"answer": None}),
        (TA, GREETING, {}),
        (TA, GREETING, {"text": ["Buenos", "días"]}),
        (WB, GREETING, {}),
        (WB, GREETING, {"tiles": "Buenos días"}),
        (WB, GREETING, {"tiles": ["Buenos", 7]}),
        (MP, None, {}),
        (MP, None, {"completed": False}),
        (MP, None, {"completed": "true"}),
    ],
)
def test_invalid_payload_raises_invalid_answer(kind, solution, payload):
    with pytest.raises(AppError) as info:
        check_answer(kind, solution, payload)
    assert info.value.status_code == 422
    assert info.value.code == "INVALID_ANSWER"
