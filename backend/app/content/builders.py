"""Exercise builders and a validator shared by every course module.

A course module exposes ``COURSE = {title, language_code, flag_emoji,
description, units: [{title, description, color, skills: [{title, icon,
lessons: [(title, [exercise, ...])]}]}]}``. ``validate_course`` enforces the
exercise contract (§5) so broken content fails fast in tests and at seed time.
"""

import re
from collections import Counter
from typing import Any

from app.models import ExerciseType
from app.services.answer_check import normalize

Ex = dict[str, Any]


def mc(prompt: str, options: list[str], answer: str, explanation: str) -> Ex:
    return {
        "type": ExerciseType.MULTIPLE_CHOICE,
        "prompt": prompt,
        "payload": {"options": options},
        "solution": {"answer": answer},
        "explanation": explanation,
    }


def wb(prompt: str, tiles: list[str], accepted: list[str], explanation: str) -> Ex:
    return {
        "type": ExerciseType.WORD_BANK,
        "prompt": prompt,
        "payload": {"tiles": tiles},
        "solution": {"accepted": accepted},
        "explanation": explanation,
    }


def mp(pairs: list[tuple[str, str]], explanation: str) -> Ex:
    return {
        "type": ExerciseType.MATCH_PAIRS,
        "prompt": "Match the pairs",
        "payload": {"pairs": [{"left": left, "right": right} for left, right in pairs]},
        "solution": None,
        "explanation": explanation,
    }


def fb(prompt: str, sentence: str, options: list[str], answer: str, explanation: str) -> Ex:
    return {
        "type": ExerciseType.FILL_BLANK,
        "prompt": prompt,
        "payload": {"sentence": sentence, "options": options},
        "solution": {"answer": answer},
        "explanation": explanation,
    }


def ta(prompt: str, accepted: list[str], explanation: str, placeholder: str | None = None) -> Ex:
    payload: dict[str, Any] = {"placeholder": placeholder} if placeholder else {}
    return {
        "type": ExerciseType.TYPE_ANSWER,
        "prompt": prompt,
        "payload": payload,
        "solution": {"accepted": accepted},
        "explanation": explanation,
    }


# ── Validation ───────────────────────────────────────────────────────────────

_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _check(condition: bool, where: str, message: str) -> None:
    if not condition:
        raise ValueError(f"{where}: {message}")


def _validate_exercise(ex: Ex, where: str) -> None:
    kind = ex["type"]
    payload, solution = ex["payload"], ex["solution"]
    _check(bool(ex["prompt"].strip()), where, "empty prompt")
    _check(bool((ex.get("explanation") or "").strip()), where, "missing explanation")

    if kind in (ExerciseType.MULTIPLE_CHOICE, ExerciseType.FILL_BLANK):
        options = payload["options"]
        _check(len(options) >= 3, where, "needs at least 3 options")
        _check(len({normalize(o) for o in options}) == len(options), where, "duplicate options")
        _check(solution["answer"] in options, where, f"answer {solution['answer']!r} not in options")
        if kind is ExerciseType.FILL_BLANK:
            _check(payload["sentence"].count("___") == 1, where, "sentence needs exactly one ___")
    elif kind is ExerciseType.WORD_BANK:
        accepted = solution["accepted"]
        _check(bool(accepted), where, "no accepted answers")
        words = Counter(normalize(accepted[0]).split())
        # A tile may hold several words once normalized (e.g. "Est-ce" -> "est ce").
        tiles = Counter(word for t in payload["tiles"] for word in normalize(t).split())
        _check(not (words - tiles), where, f"tiles can't build {accepted[0]!r} (missing {dict(words - tiles)})")
        distractors = sum(tiles.values()) - sum(words.values())
        _check(1 <= distractors <= 3, where, f"needs 1-3 distractor tiles, has {distractors}")
        in_order = " ".join(normalize(t) for t in payload["tiles"][: sum(words.values())])
        _check(in_order != normalize(accepted[0]), where, "tiles are already in answer order")
    elif kind is ExerciseType.MATCH_PAIRS:
        pairs = payload["pairs"]
        _check(3 <= len(pairs) <= 5, where, "needs 3-5 pairs")
        _check(solution is None, where, "match pairs must not have a solution")
        for side in ("left", "right"):
            values = [normalize(p[side]) for p in pairs]
            _check(len(set(values)) == len(values), where, f"duplicate {side} values")
    elif kind is ExerciseType.TYPE_ANSWER:
        _check(bool(solution["accepted"]), where, "no accepted answers")
        _check(all(normalize(a) for a in solution["accepted"]), where, "empty accepted answer")
    else:
        raise ValueError(f"{where}: unknown type {kind}")


def validate_course(course: dict[str, Any]) -> None:
    """Raise ValueError describing the first contract violation, if any."""
    name = course.get("title", "?")
    for key in ("title", "language_code", "flag_emoji", "description", "units"):
        _check(bool(course.get(key)), name, f"missing {key}")
    for u, unit in enumerate(course["units"], start=1):
        _check(bool(_HEX.match(unit["color"])), f"{name} unit {u}", "color must be #RRGGBB")
        _check(bool(unit["skills"]), f"{name} unit {u}", "no skills")
        unit_types: set[ExerciseType] = set()
        for skill in unit["skills"]:
            _check(bool(skill["title"] and skill["icon"]), f"{name} unit {u}", "skill needs title and icon")
            _check(bool(skill["lessons"]), f"{name}/{skill['title']}", "no lessons")
            for title, exercises in skill["lessons"]:
                where = f"{name}/{skill['title']}/{title}"
                _check(5 <= len(exercises) <= 7, where, f"needs 5-7 exercises, has {len(exercises)}")
                types = {ex["type"] for ex in exercises}
                _check(len(types) >= 3, where, "needs at least 3 exercise types")
                unit_types |= types
                for i, ex in enumerate(exercises, start=1):
                    _validate_exercise(ex, f"{where} #{i}")
        if u == 1:
            _check(len(unit_types) == len(ExerciseType), f"{name} unit 1", "must use all 5 exercise types")
