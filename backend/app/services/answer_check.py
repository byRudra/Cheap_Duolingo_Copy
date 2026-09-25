"""Server-side answer validation (§5)."""

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from app.errors import AppError
from app.models import ExerciseType

_PUNCTUATION = re.compile(r"[.,!?¿¡]")
_WHITESPACE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """lowercase → trim → collapse whitespace → strip ``.,!?¿¡``.

    NFC first, so an accent typed as a combining mark (e.g. "o" + U+0301)
    compares equal to the precomposed "ó".
    """
    text = _PUNCTUATION.sub("", unicodedata.normalize("NFC", text).lower())
    return _WHITESPACE.sub(" ", text).strip()


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


@dataclass(frozen=True)
class CheckResult:
    correct: bool
    correct_answer: str | None
    note: str | None = None


def _invalid(message: str) -> AppError:
    return AppError(422, "INVALID_ANSWER", message)


def _require_str(answer: dict[str, Any], key: str) -> str:
    value = answer.get(key)
    if not isinstance(value, str):
        raise _invalid(f"Answer must include a '{key}' string.")
    return value


def match_text(submitted: str, accepted: list[str], accent_tolerant: bool) -> CheckResult:
    """Compare free text against accepted answers, optionally forgiving accents."""
    given = normalize(submitted)
    for option in accepted:
        if given == normalize(option):
            return CheckResult(True, accepted[0])
    if accent_tolerant:
        bare = strip_accents(given)
        for option in accepted:
            if bare == strip_accents(normalize(option)):
                return CheckResult(True, accepted[0], f"Watch your accents: {option}")
    return CheckResult(False, accepted[0])


def check_answer(
    exercise_type: ExerciseType,
    solution: dict[str, Any] | None,
    answer: dict[str, Any],
) -> CheckResult:
    match exercise_type:
        case ExerciseType.MULTIPLE_CHOICE | ExerciseType.FILL_BLANK:
            assert solution is not None
            given = _require_str(answer, "answer")
            expected = solution["answer"]
            return CheckResult(normalize(given) == normalize(expected), expected)
        case ExerciseType.WORD_BANK:
            assert solution is not None
            tiles = answer.get("tiles")
            if not isinstance(tiles, list) or not all(isinstance(t, str) for t in tiles):
                raise _invalid("Answer must include 'tiles' as a list of strings.")
            return match_text(" ".join(tiles), solution["accepted"], accent_tolerant=True)
        case ExerciseType.TYPE_ANSWER:
            assert solution is not None
            text = _require_str(answer, "text")
            return match_text(text, solution["accepted"], accent_tolerant=True)
        case ExerciseType.MATCH_PAIRS:
            # Validated on the client for instant per-tap feedback (documented trade-off).
            if answer.get("completed") is not True:
                raise _invalid("Match pairs answers must send {'completed': true}.")
            return CheckResult(True, None)
    raise _invalid(f"Unsupported exercise type {exercise_type}.")
