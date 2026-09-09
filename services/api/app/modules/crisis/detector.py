import re
from collections.abc import Iterable, Mapping

DEFAULT_CRISIS_MARKERS: dict[str, tuple[str, ...]] = {
    "physical_violence": (
        "меня бьют",
        "меня избили",
        "физическое насилие",
        "they hit me",
        "physical violence",
    ),
    "threat_to_life": (
        "угрожают убить",
        "угроза моей жизни",
        "хотят меня убить",
        "threatened to kill me",
        "threat to my life",
    ),
    "self_harm": (
        "хочу умереть",
        "покончить с собой",
        "навредить себе",
        "суицид",
        "want to die",
        "kill myself",
        "hurt myself",
    ),
}


class CrisisDetector:
    """Conservative, deterministic phrase matching with no retained match details."""

    def __init__(self, markers: Mapping[str, Iterable[str]] | None = None) -> None:
        source = markers or DEFAULT_CRISIS_MARKERS
        self._markers = tuple(
            self._normalize(marker)
            for group in source.values()
            for marker in group
            if marker.strip()
        )

    def detect(self, values: Iterable[str | None]) -> bool:
        for value in values:
            if not value:
                continue
            normalized = self._normalize(value)
            if any(marker in normalized for marker in self._markers):
                return True
        return False

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value.casefold()).strip()
