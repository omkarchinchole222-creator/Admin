from dataclasses import dataclass


@dataclass
class ClipSegment:
    start: float
    end: float
    text: str
    emotion: str
    score: float

    @property
    def duration(self) -> float:
        return self.end - self.start
