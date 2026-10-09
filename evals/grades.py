"""Grades of drafts on the scale in evals/README.md, one file per results folder and grader:
evals/grades/<results>.<grader>.json, e.g. mini-v1.claude.json or mini-v1.human.json."""

from pathlib import Path

from pydantic import BaseModel, Field

from evals.cases import EVALS_DIR

GRADES_DIR = EVALS_DIR / "grades"
Score = int  # 0, 1 or 2


class Grade(BaseModel):
    grounding: Score = Field(ge=0, le=2)
    relevance: Score = Field(ge=0, le=2)
    naturalness: Score = Field(ge=0, le=2)
    note: str = ""

    @property
    def good(self) -> bool:
        """Sendable after light editing at most: fully grounded and 5 or 6 points of 6."""
        return self.grounding == 2 and self.grounding + self.relevance + self.naturalness >= 5


class GradeFile(BaseModel):
    grader: str
    graded_at: str
    scale: str
    scope: str
    grades: dict[str, Grade]  # "<case>.<repeat>" -> grade


def grades_path(results: str, grader: str, directory: Path = GRADES_DIR) -> Path:
    return directory / f"{results}.{grader}.json"


def load_grades(results: str, grader: str, directory: Path = GRADES_DIR) -> dict[str, Grade] | None:
    path = grades_path(results, grader, directory)
    if not path.exists():
        return None
    return GradeFile.model_validate_json(path.read_text(encoding="utf-8")).grades
