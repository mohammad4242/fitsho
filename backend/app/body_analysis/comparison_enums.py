from enum import StrEnum


class BodyProgressState(StrEnum):
    IMPROVED = "improved"
    UNCHANGED = "unchanged"
    DECLINED_OR_LESS_BALANCED = "declined_or_less_balanced"
    UNCERTAIN = "uncertain"
