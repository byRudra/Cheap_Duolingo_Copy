"""Server-side answer validation (§5)."""

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from app.errors import AppError
from app.models import ExerciseType

# Sentence punctuation incl. the Gurmukhi danda (U+0964) and double danda (U+0965).
_PUNCTUATION = re.compile("[.,!?¿¡%s%s]" % (chr(0x0964), chr(0x0965)))
_WHITESPACE = re.compile(r"\s+")
# Combining Diacritical Marks block: the accents of Latin-script languages.
# Other scripts' vowel signs (e.g. Gurmukhi matras) are spelling, not accents.
_LATIN_ACCENTS = re.compile("[%s-%s]" % (chr(0x0300), chr(0x036F)))


def normalize(text: str) -> str:
    """lowercase → trim → collapse whitespace → strip ``.,!?¿¡।`` (hyphens → spaces).

    NFC first, so an accent typed as a combining mark (e.g. "o" + U+0301)
    compares equal to the precomposed "ó".
    """
    text = unicodedata.normalize("NFC", text).lower().replace(chr(0x2019), "'")  # curly apostrophe
    text = _PUNCTUATION.sub("", text).replace("-", " ")  # "parlez-vous" == "parlez vous"
    return _WHITESPACE.sub(" ", text).strip()


def strip_accents(text: str) -> str:
    """Remove Latin diacritics (é → e, ñ → n) and nothing else."""
    stripped = _LATIN_ACCENTS.sub("", unicodedata.normalize("NFD", text))
    return unicodedata.normalize("NFC", stripped)


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
