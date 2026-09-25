"""Course registry. The first course is the demo learner's default."""

from typing import Any

from app.content.english import COURSE as ENGLISH
from app.content.french import COURSE as FRENCH
from app.content.punjabi import COURSE as PUNJABI
from app.content.spanish import COURSE as SPANISH

COURSES: list[dict[str, Any]] = [SPANISH, FRENCH, PUNJABI, ENGLISH]
