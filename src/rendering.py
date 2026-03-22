from dataclasses import asdict
import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from models import (
    DiscussionTurn,
    GameRecord,
    MultiGameRecord,
    PlayerRecord,
    ReflectionRecord,
    ResolutionRecord,
    VoteRecord,
)


TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=True,
)


def render_html(record: GameRecord) -> str:
    template = _env.get_template("game_report.html")

    player_classes = {
        player.name: f"player-{index}"
        for index, player in enumerate(record.players, start=1)
    }
    player_roles = {player.name: player.role for player in record.players}
    player_words = {player.name: player.word for player in record.players}

    all_models = [player.model for player in record.players]
    has_any_model = any(all_models)
    unique_models = set(m for m in all_models if m)
    all_same_model = has_any_model and len(unique_models) == 1
    shared_model = next(iter(unique_models)) if all_same_model else None
    show_model_in_chip = has_any_model and not all_same_model

    sorted_tally = sorted(record.tally.items(), key=lambda item: (-item[1], item[0]))

    return template.render(
        record=record,
        player_classes=player_classes,
        player_roles=player_roles,
        player_words=player_words,
        shared_model=shared_model,
        show_model_in_chip=show_model_in_chip,
        sorted_tally=sorted_tally,
    )


def game_record_json(record: GameRecord) -> str:
    return json.dumps(asdict(record), ensure_ascii=False, indent=2)


def multi_game_record_json(record: MultiGameRecord) -> str:
    return json.dumps(asdict(record), ensure_ascii=False, indent=2)


def output_artifact(label: str, content: str, filename: str | None) -> None:
    if filename:
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"\n--- {label} saved to {path} ---")


def parse_game_record(data: dict) -> GameRecord:
    players = [PlayerRecord(**p) for p in data.get("players", [])]
    discussion = [DiscussionTurn(**d) for d in data.get("discussion", [])]
    votes = [VoteRecord(**v) for v in data.get("votes", [])]
    resolution = ResolutionRecord(**data["resolution"]) if data.get("resolution") else None
    reflections = [ReflectionRecord(**r) for r in data.get("reflections", [])]
    return GameRecord(
        players=players,
        wolf_count=data.get("wolf_count", 0),
        citizen_word=data.get("citizen_word", ""),
        wolf_word=data.get("wolf_word", ""),
        rounds=data.get("rounds", 0),
        discussion=discussion,
        votes=votes,
        tally=data.get("tally", {}),
        resolution=resolution,
        reflections=reflections,
        game_id=data.get("game_id"),
        seed=data.get("seed"),
        timestamp=data.get("timestamp"),
        language=data.get("language"),
        show_advice=data.get("show_advice", True),
    )


def build_replay_filename(
    timestamp: str,
    extension: str,
    output_dir: str = "../replay",
    game_number: int | None = None,
) -> str:
    suffix = f"_game{game_number:02d}" if game_number is not None else ""
    return f"{output_dir}/wordwolf_replay_{timestamp}{suffix}.{extension}"
