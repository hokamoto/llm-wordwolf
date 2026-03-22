from dataclasses import dataclass, field
from typing import Any


PLAYER_NAMES = [
    "Alice",
    "Bob",
    "Charlie",
    "Diana",
    "Eve",
    "Frank",
    "Grace",
    "Heidi",
    "Ivan",
    "Judy",
]


def normalize_prompt_language(language: str | None) -> str | None:
    if not language:
        return None
    return language.capitalize()


def display_name(player: dict[str, Any]) -> str:
    return f"{player['name']}(Wolf)" if player["role"] == "wolf" else player["name"]


def build_display_name_map(players: list[dict[str, Any]]) -> dict[str, str]:
    return {player["name"]: display_name(player) for player in players}


@dataclass
class PlayerRecord:
    name: str
    role: str
    word: str
    model: str | None = None


@dataclass
class DiscussionTurn:
    round_number: int
    speaker: str
    thinking: str | None
    statement: str


@dataclass
class VoteRecord:
    voter: str
    thinking: str | None
    vote_target: str
    attempts: int
    used_random_fallback: bool


@dataclass
class ResolutionRecord:
    eliminated_name: str
    eliminated_role: str
    wolf_guess: str | None
    wolf_guess_thinking: str | None
    winner: str
    summary: str


@dataclass
class ReflectionRecord:
    player_name: str
    player_role: str
    reflection: str
    lessons_learned: str | None = None


@dataclass
class GameRecord:
    players: list[PlayerRecord]
    wolf_count: int
    citizen_word: str
    wolf_word: str
    rounds: int
    discussion: list[DiscussionTurn]
    votes: list[VoteRecord]
    tally: dict[str, int]
    resolution: ResolutionRecord | None = None
    reflections: list[ReflectionRecord] = field(default_factory=list)
    game_id: str | None = None
    seed: int | None = None
    timestamp: str | None = None
    language: str | None = None
    show_advice: bool = True


@dataclass
class GameConfig:
    num_players: int = 3
    num_wolves: int = 1
    num_rounds: int = 2
    language: str | None = None
    show_thinking: bool = True
    show_advice: bool = True
    human_name: str | None = None
    game_id: str | None = None
    seed: int | None = None
    model_list: list[str] | None = None
    wolf_indices: list[int] | None = None
    word_pair_index: int | None = None
    word_pair: tuple[str, str] | None = None
    generate_word_pair: bool = False
    run_reflection: bool = False
    output_dir: str = "../replay"
    prior_lessons_by_player: dict[str, str] = field(default_factory=dict)


@dataclass
class PlayerLessonsHistoryEntry:
    game_number: int
    lessons_learned: str


@dataclass
class PlayerStats:
    player_name: str
    citizen_games: int = 0
    wolf_games: int = 0
    total_wins: int = 0
    citizen_wins: int = 0
    wolf_wins: int = 0
    citizen_win_rate: float = 0.0
    wolf_win_rate: float = 0.0
    eliminated_games: int = 0
    eliminated_as_wolf_games: int = 0
    wolf_guess_successes: int = 0
    citizen_vote_hits: int = 0
    citizen_vote_total: int = 0
    citizen_vote_hit_rate: float = 0.0


@dataclass
class MultiGameRecord:
    games: list[GameRecord]
    player_stats: list[PlayerStats]
    lessons_history: dict[str, list[PlayerLessonsHistoryEntry]] = field(default_factory=dict)
    game_id: str | None = None
    seed: int | None = None
    games_count: int = 0
    started_at: str | None = None
    completed_at: str | None = None
