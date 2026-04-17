from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Segment:
    start: float
    end: float
    scene_score: float
    speech_score: float
    emotion_score: float
    movement_score: float
    hook_score: float
    rewatch_score: float
    category: str

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    @property
    def total_score(self) -> float:
        return (
            0.22 * self.hook_score
            + 0.22 * self.emotion_score
            + 0.2 * self.movement_score
            + 0.18 * self.rewatch_score
            + 0.1 * self.scene_score
            + 0.08 * self.speech_score
        )


@dataclass
class ClipOutput:
    path: Path
    start: float
    end: float
    score: float
    category: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "file": self.path.name,
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "score": round(self.score, 4),
            "category": self.category,
        }
