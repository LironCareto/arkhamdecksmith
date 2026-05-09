from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


GameMode = Literal["one_shot", "campaign", "standalone"]
DeckRole = Literal[
    "fighter",
    "cluever",
    "flex",
    "support",
    "evader",
    "enemy_management",
]


@dataclass(frozen=True)
class BuildRequest:
    raw_request: str
    player_count: int
    game_mode: GameMode
    xp_budget: int
    required_classes: list[str] = field(default_factory=list)
    required_investigators: list[str] = field(default_factory=list)
    preferred_roles: list[DeckRole] = field(default_factory=list)
    taboo: bool = False
    collection_filter: str | None = None


@dataclass(frozen=True)
class CardRole:
    card_code: str
    card_name: str
    primary_role: str | None = None
    secondary_roles: list[str] = field(default_factory=list)
    mechanics: list[str] = field(default_factory=list)
    economy_tags: list[str] = field(default_factory=list)
    tempo_tags: list[str] = field(default_factory=list)
    synergy_tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DeckCandidate:
    investigator_code: str
    investigator_name: str
    intended_role: DeckRole
    cards: dict[str, int]
    xp_spent: int = 0
    rationale: str = ""


@dataclass(frozen=True)
class ValidationIssue:
    severity: Literal["error", "warning"]
    code: str
    message: str
    card_code: str | None = None


@dataclass(frozen=True)
class ValidationReport:
    is_valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]


@dataclass(frozen=True)
class DeckProfile:
    investigator_code: str
    investigator_name: str
    card_count: int
    asset_count: int
    event_count: int
    skill_count: int
    total_cost: int
    average_cost: float
    role_counts: dict[str, int] = field(default_factory=dict)
    mechanic_counts: dict[str, int] = field(default_factory=dict)
    economy_score: float = 0.0
    clue_score: float = 0.0
    combat_score: float = 0.0
    defense_score: float = 0.0


@dataclass(frozen=True)
class PartyProfile:
    decks: list[DeckProfile]
    player_count: int
    clue_score: float
    combat_score: float
    economy_score: float
    defense_score: float
    warnings: list[str] = field(default_factory=list)