from __future__ import annotations

import re

from core.models import BuildRequest


KNOWN_CLASSES = {
    "guardian",
    "seeker",
    "rogue",
    "mystic",
    "survivor",
}

KNOWN_INVESTIGATORS = {
    "roland banks",
    "daisy walker",
    "skids o'toole",
    "agnes baker",
    "wendy adams",
    "ashcan pete",
    "jenny barnes",
    "silas marsh",
    "norman withers",
    "daniela reyes",
}

NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def detect_player_count(text: str) -> int:
    digit_match = re.search(r"\b(\d+)\b", text)

    if digit_match:
        return int(digit_match.group(1))

    for word, value in NUMBER_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", text):
            return value

    return 1


def detect_game_mode(text: str) -> str:
    if "campaign" in text:
        return "campaign"

    if "standalone" in text:
        return "standalone"

    if "one-shot" in text or "oneshot" in text:
        return "one_shot"

    return "campaign"


def detect_xp_budget(text: str) -> int:
    xp_match = re.search(r"(\d+)\s*xp", text)

    if xp_match:
        return int(xp_match.group(1))

    if "0 xp" in text:
        return 0

    if "zero xp" in text:
        return 0

    return 0


def detect_required_classes(text: str) -> list[str]:
    found = []

    for class_name in KNOWN_CLASSES:
        if re.search(rf"\b{re.escape(class_name)}\b", text):
            found.append(class_name)

    return found


def detect_required_investigators(text: str) -> list[str]:
    found = []

    for investigator_name in KNOWN_INVESTIGATORS:
        if investigator_name in text:
            found.append(investigator_name)

    return found


def detect_taboo(text: str) -> bool:
    return "taboo" in text


def parse_build_request(request_text: str) -> BuildRequest:
    normalized = normalize_text(request_text)

    player_count = detect_player_count(normalized)

    required_classes = detect_required_classes(normalized)
    required_investigators = detect_required_investigators(normalized)

    return BuildRequest(
        raw_request=request_text,
        player_count=player_count,
        game_mode=detect_game_mode(normalized),
        xp_budget=detect_xp_budget(normalized),
        required_classes=required_classes,
        required_investigators=required_investigators,
        taboo=detect_taboo(normalized),
    )