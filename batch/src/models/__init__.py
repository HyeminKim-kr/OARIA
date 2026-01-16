"""데이터 모델"""

from .paper import (
    Author,
    DisplayContent,
    DisplayFigure,
    DisplayParagraph,
    DisplaySection,
    Figure,
    Paper,
    Section,
)

__all__ = [
    "Paper",
    "Author",
    "Section",
    "DisplaySection",
    "DisplayContent",
    "DisplayParagraph",
    "DisplayFigure",
    "Figure",
]
