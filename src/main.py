import argparse
import asyncio
import json
import os
import random
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from engine import GameEngine
from models import (
    GameConfig,
    GameRecord,
    MultiGameRecord,
    PlayerLessonsHistoryEntry,
    PlayerStats,
    display_name,
)
from rendering import (
    build_replay_filename,
    game_record_json,
    multi_game_record_json,
    output_artifact,
    parse_game_record,
    render_html,
)
from word_pairs import WORD_PAIRS


class CLIEventHandler:
    def on_game_start(self, players, citizen_word, wolf_word, num_rounds, human_name, model_map=None):
        print("=" * 50)
        print("  WORD WOLF - LLM Multi-Agent Game")
        print("=" * 50)

        def player_label(p):
            name = display_name(p) if not human_name else p["name"]
            if model_map and p["name"] in model_map:
                return f"{name} [{model_map[p['name']]}]"
            return name

        if human_name:
            human_player = next(p for p in players if p["name"] == human_name)
            print(f"\n  Players: {', '.join(player_label(p) for p in players)}")
            print(f"  Rounds: {num_rounds}")
            print(f"  Your word: {human_player['word']}")
        else:
            print(f"\n  Players: {', '.join(player_label(p) for p in players)}")
            print(f"  Citizen word: {citizen_word}")
            print(f"  Wolf team word: {wolf_word}")
            print(f"  Rounds: {num_rounds}")

    def on_discussion_start(self):
        print(f"\n{'=' * 50}")
        print("  Discussion")
        print(f"{'=' * 50}")

    def on_discussion_turn(self, speaker_name, thinking, statement, show_thinking):
        if show_thinking:
            print(f"  [{speaker_name}'s thinking] {thinking}")
        print(f"  {speaker_name}: {statement}")
        print()

    def on_human_discussion_prompt(self, speaker_name, word, round_num, total_rounds):
        remaining = total_rounds - round_num + 1
        remaining_str = f"  [Round {round_num}/{total_rounds} — {remaining} round(s) remaining]"
        print(remaining_str)
        print(f"  (Your word: {word})")
        print(f"  {speaker_name}'s turn to speak:")

    def on_voting_start(self):
        print(f"\n{'=' * 50}")
        print("  VOTING PHASE")
        print(f"{'=' * 50}")

    def on_vote_cast(self, voter_display, thinking, vote_target_display, show_thinking, used_random_fallback):
        print(f"\n--- {voter_display} votes ---")
        if show_thinking:
            print(f"  [THINKING] {thinking}")
        if used_random_fallback:
            print("  Max retries reached, random fallback.")
        print(f"  {voter_display} votes for: {vote_target_display}")

    def on_vote_tally(self, tally, display_names):
        print("\n--- Vote Tally ---")
        for name, count in sorted(tally.items(), key=lambda item: (-item[1], item[0])):
            print(f"  {display_names.get(name, name)}: {count} vote(s)")

    def on_resolution_start(self):
        print(f"\n{'=' * 50}")
        print("  RESOLUTION")
        print(f"{'=' * 50}")

    def on_elimination(self, eliminated_display, role):
        print(f"\n  {eliminated_display} was eliminated!")
        print(f"  {eliminated_display}'s role: {role.upper()}")

    def on_wolf_found(self):
        print("\n  A wolf was found! The eliminated wolf gets one chance to guess the citizen word...")

    def on_wolf_guess(self, eliminated_display, guess_text, citizen_word, guess_thinking, show_thinking):
        if show_thinking and guess_thinking:
            print(f"  [THINKING] {guess_thinking}")
            print()
        print(f"  {eliminated_display} guesses: {guess_text}")
        print(f"  Citizen word was: {citizen_word}")

    def on_judge_result(self, is_correct, show_thinking):
        if show_thinking:
            print(f"  [JUDGE] is_correct={is_correct}")

    def on_game_result(self, summary, winner):
        print(f"\n  {summary}")

    def on_citizen_eliminated(self, summary):
        print("\n  A citizen was eliminated...")
        print(f"\n  {summary}")

    def on_reflection_start(self):
        print(f"\n{'=' * 50}")
        print("  POST-GAME REFLECTIONS")
        print(f"{'=' * 50}")

    def on_reflection(self, speaker_name, reflection, lessons_learned):
        print(f"  {speaker_name}: {reflection}")
        if lessons_learned:
            print(f"  [Lessons Learned] {lessons_learned}")
        print()

    def on_game_reveal(self, citizen_word, wolf_word, players):
        print(f"\n{'=' * 50}")
        print("  GAME REVEAL")
        print(f"{'=' * 50}")
        print(f"  Citizen word: {citizen_word}")
        print(f"  Wolf team word: {wolf_word}")
        print("  Roles:")
        for p in players:
            print(f"    {p['name']}: {p['role'].upper()}")

    def on_generate_word_pair(self):
        print("  Generating word pair using LLM...")


class CLIInputProvider:
    def get_player_name(self) -> str:
        sys.stdout.write("Enter your name: ")
        sys.stdout.flush()
        return sys.stdin.buffer.readline().decode("utf-8", errors="ignore").strip()

    def get_discussion_input(self, player_name: str, word: str, round_num: int, total_rounds: int) -> str:
        sys.stdout.write("  > ")
        sys.stdout.flush()
        statement = sys.stdin.buffer.readline().decode("utf-8", errors="ignore").strip()
        print()
        return statement

    def get_vote_input(self, player_name: str, candidates: list[str]) -> str:
        print(f"\n  Candidates: {', '.join(candidates)}")
        while True:
            sys.stdout.write("  Vote for: ")
            sys.stdout.flush()
            choice = sys.stdin.buffer.readline().decode("utf-8", errors="ignore").strip()
            if choice in candidates:
                return choice
            print(f"  Invalid choice. Please choose from: {', '.join(candidates)}")

    def get_wolf_guess_input(self, player_name: str) -> str:
        return input("  Guess the citizen word: ").strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Word Wolf LLM Game")
    parser.add_argument("--players", type=int, default=3, help="Number of players (3-10)")
    parser.add_argument("--wolves", type=int, default=1, help="Number of wolves (1 to floor(players / 2))")
    parser.add_argument("--rounds", type=int, default=2, help="Number of discussion rounds")
    parser.add_argument("--games", type=int, default=None, help="Number of games to run in sequence")
    parser.add_argument("--lang", type=str, default=None, help="Language to use for discussion")
    parser.add_argument("--hide-thinking", action="store_true", help="Hide thinking output")
    parser.add_argument("--no-advice", action="store_true", help="Hide strategy advices from the Discuss prompt")
    parser.add_argument("--reflection", action="store_true", help="Run post-game reflection phase")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Save the full game record to wordwolf_replay_[timestamp].json",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Save the full game record to wordwolf_replay_[timestamp].html",
    )
    parser.add_argument("--models", type=str, default=None, help="Comma-separated OpenRouter model IDs, one per player")
    parser.add_argument("--wolf-indices", type=str, default=None, help="Comma-separated wolf player indices (0-based)")
    parser.add_argument("--word-pair-index", type=int, default=None, help="Index into WORD_PAIRS (0-based)")
    parser.add_argument("--word-pair", type=str, nargs=2, metavar=("CITIZEN_WORD", "WOLF_WORD"), default=None, help="Specify word pair directly; first word goes to citizens, second to wolves (no shuffle)")
    parser.add_argument("--generate-word-pair", action="store_true", help="Generate word pair using LLM instead of selecting from predefined list")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    parser.add_argument("--game-id", type=str, default=None, help="Experiment game identifier included in JSON output")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory for replay files (default: ../replay)")
    parser.add_argument("--human", action="store_true", help="Join the game as a human player")
    parser.add_argument("--prompt-debug", action="store_true", help="Enable prompt debug logging")
    parser.add_argument(
        "--continue",
        type=str,
        metavar="JSON_FILE",
        dest="continue_json",
        help="Continue from a previously saved JSON file. Requires --games. Inherits all game settings.",
    )
    return parser


_CONTINUE_CONFLICTING_ARGS = {
    "players": 3,
    "wolves": 1,
    "rounds": 2,
    "models": None,
    "lang": None,
    "word_pair": None,
    "word_pair_index": None,
    "generate_word_pair": False,
    "no_advice": False,
    "reflection": False,
    "wolf_indices": None,
    "human": False,
}


def validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> tuple[int, int, list[str] | None, list[int] | None, tuple[str, str] | None]:
    games_explicitly_set = args.games is not None
    if args.games is None:
        args.games = 1

    if args.continue_json:
        if not games_explicitly_set:
            parser.error("--continue requires --games to be explicitly specified")
        if args.games < 1:
            parser.error("--games must be at least 1")
        for arg_name, default_val in _CONTINUE_CONFLICTING_ARGS.items():
            if getattr(args, arg_name) != default_val:
                cli_name = f"--{arg_name.replace('_', '-')}"
                parser.error(f"{cli_name} cannot be used with --continue (settings are inherited from JSON)")
        json_path = Path(args.continue_json)
        if not json_path.is_file():
            parser.error(f"--continue file not found: {args.continue_json}")
        return 0, 0, None, None, None

    if args.human and args.wolf_indices is not None:
        parser.error("--human and --wolf-indices cannot be used together")
    if args.human:
        args.hide_thinking = True

    if not 3 <= args.players <= 10:
        parser.error("--players must be between 3 and 10")
    if args.games < 1:
        parser.error("--games must be at least 1")

    num_players = args.players
    max_wolves = num_players // 2
    if not 1 <= args.wolves <= max_wolves:
        parser.error(f"--wolves must be between 1 and {max_wolves} when --players is {num_players}")

    model_list = None
    if args.models:
        model_list = [m.strip() for m in args.models.split(",")]
        if len(model_list) == 1:
            model_list = model_list * num_players
        elif len(model_list) != num_players:
            parser.error(f"--models must have exactly 1 or {num_players} entries (got {len(model_list)})")

    wolf_indices = None
    if args.wolf_indices is not None:
        wolf_indices = [int(x.strip()) for x in args.wolf_indices.split(",")]
        if len(wolf_indices) != args.wolves:
            parser.error(f"--wolf-indices must have exactly {args.wolves} entries (got {len(wolf_indices)})")
        for idx in wolf_indices:
            if not 0 <= idx < num_players:
                parser.error(f"Wolf index {idx} out of range [0, {num_players - 1}]")

    if args.word_pair_index is not None and args.word_pair is not None:
        parser.error("--word-pair-index and --word-pair cannot be used together")
    if args.generate_word_pair and (args.word_pair is not None or args.word_pair_index is not None):
        parser.error("--generate-word-pair cannot be used with --word-pair or --word-pair-index")
    if args.word_pair_index is not None and not 0 <= args.word_pair_index < len(WORD_PAIRS):
        parser.error(f"--word-pair-index must be between 0 and {len(WORD_PAIRS) - 1}")

    word_pair = tuple(args.word_pair) if args.word_pair else None
    return num_players, max(1, args.rounds), model_list, wolf_indices, word_pair


def make_config(
    args: argparse.Namespace,
    num_players: int,
    num_rounds: int,
    model_list: list[str] | None,
    wolf_indices: list[int] | None,
    word_pair: tuple[str, str] | None,
    human_name: str | None,
    prior_lessons_by_player: dict[str, str],
) -> GameConfig:
    return GameConfig(
        num_players=num_players,
        num_wolves=args.wolves,
        num_rounds=num_rounds,
        language=args.lang,
        show_thinking=not args.hide_thinking,
        show_advice=not args.no_advice,
        human_name=human_name,
        game_id=args.game_id,
        seed=args.seed,
        model_list=model_list,
        wolf_indices=wolf_indices,
        word_pair_index=args.word_pair_index,
        word_pair=word_pair,
        generate_word_pair=args.generate_word_pair,
        run_reflection=args.reflection,
        output_dir=args.output_dir or "../replay",
        prior_lessons_by_player=dict(prior_lessons_by_player),
    )


def update_lessons_history(
    game_number: int,
    game_record,
    prior_lessons_by_player: dict[str, str],
    lessons_history: dict[str, list[PlayerLessonsHistoryEntry]],
) -> None:
    for reflection in game_record.reflections:
        if not reflection.lessons_learned:
            continue
        prior_lessons_by_player[reflection.player_name] = reflection.lessons_learned
        lessons_history.setdefault(reflection.player_name, []).append(
            PlayerLessonsHistoryEntry(
                game_number=game_number,
                lessons_learned=reflection.lessons_learned,
            )
        )


@dataclass
class ContinueState:
    num_players: int
    num_wolves: int
    num_rounds: int
    language: str | None
    show_advice: bool
    model_list: list[str] | None
    run_reflection: bool
    game_id: str | None
    prior_game_records: list[GameRecord]
    prior_lessons_by_player: dict[str, str]
    lessons_history: dict[str, list[PlayerLessonsHistoryEntry]]
    used_word_pairs: set[frozenset[str]]
    started_at: str | None


def load_continue_state(json_path: str) -> ContinueState:
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    is_multi = "games" in data
    if is_multi:
        game_dicts = data["games"]
        game_id = data.get("game_id")
        started_at = data.get("started_at")
    else:
        game_dicts = [data]
        game_id = data.get("game_id")
        started_at = data.get("timestamp")

    prior_game_records = [parse_game_record(g) for g in game_dicts]

    ref_game = game_dicts[0]
    ref_players = ref_game.get("players", [])
    num_players = len(ref_players)
    num_wolves = ref_game.get("wolf_count", 1)
    num_rounds = ref_game.get("rounds", 2)
    language = ref_game.get("language")
    show_advice = ref_game.get("show_advice", True)

    models = [p.get("model") for p in ref_players]
    model_list = models if any(m is not None for m in models) else None

    has_reflections = any(len(g.get("reflections", [])) > 0 for g in game_dicts)

    # Rebuild prior_lessons_by_player from reflections
    prior_lessons_by_player: dict[str, str] = {}
    lessons_history: dict[str, list[PlayerLessonsHistoryEntry]] = {}
    if is_multi and "lessons_history" in data and data["lessons_history"]:
        for player_name, entries in data["lessons_history"].items():
            for entry in entries:
                lessons_history.setdefault(player_name, []).append(
                    PlayerLessonsHistoryEntry(
                        game_number=entry["game_number"],
                        lessons_learned=entry["lessons_learned"],
                    )
                )
                prior_lessons_by_player[player_name] = entry["lessons_learned"]
    else:
        for game_num, game_dict in enumerate(game_dicts, start=1):
            for refl in game_dict.get("reflections", []):
                if refl.get("lessons_learned"):
                    player_name = refl["player_name"]
                    prior_lessons_by_player[player_name] = refl["lessons_learned"]
                    lessons_history.setdefault(player_name, []).append(
                        PlayerLessonsHistoryEntry(
                            game_number=game_num,
                            lessons_learned=refl["lessons_learned"],
                        )
                    )

    # Reconstruct used word pairs from game records
    used_word_pairs: set[frozenset[str]] = set()
    for g in game_dicts:
        cw = g.get("citizen_word", "")
        ww = g.get("wolf_word", "")
        if cw and ww:
            used_word_pairs.add(frozenset((cw, ww)))

    return ContinueState(
        num_players=num_players,
        num_wolves=num_wolves,
        num_rounds=num_rounds,
        language=language,
        show_advice=show_advice,
        model_list=model_list,
        run_reflection=has_reflections,
        game_id=game_id,
        prior_game_records=prior_game_records,
        prior_lessons_by_player=prior_lessons_by_player,
        lessons_history=lessons_history,
        used_word_pairs=used_word_pairs,
        started_at=started_at,
    )


def pick_unique_word_pair(
    used_word_pairs: set[frozenset[str]],
) -> tuple[str, str]:
    available = [
        pair for pair in WORD_PAIRS
        if frozenset(pair) not in used_word_pairs
    ]
    if not available:
        used_word_pairs.clear()
        available = list(WORD_PAIRS)
    chosen = random.choice(available)
    return random.sample(chosen, k=2)


def build_player_stats(game_records: list) -> list[PlayerStats]:
    stats_by_player: dict[str, PlayerStats] = {}

    for game_record in game_records:
        role_by_player = {player.name: player.role for player in game_record.players}
        winners_role = "citizen" if game_record.resolution and game_record.resolution.winner == "citizens" else "wolf"
        wolf_players = {player.name for player in game_record.players if player.role == "wolf"}

        for player in game_record.players:
            stats = stats_by_player.setdefault(player.name, PlayerStats(player_name=player.name))
            if player.role == "citizen":
                stats.citizen_games += 1
            else:
                stats.wolf_games += 1

            if player.role == winners_role:
                stats.total_wins += 1
                if player.role == "citizen":
                    stats.citizen_wins += 1
                else:
                    stats.wolf_wins += 1

        resolution = game_record.resolution
        if resolution is not None:
            eliminated_stats = stats_by_player.setdefault(
                resolution.eliminated_name,
                PlayerStats(player_name=resolution.eliminated_name),
            )
            eliminated_stats.eliminated_games += 1
            if resolution.eliminated_role == "wolf":
                eliminated_stats.eliminated_as_wolf_games += 1
                if resolution.winner == "wolves" and resolution.wolf_guess is not None:
                    eliminated_stats.wolf_guess_successes += 1

        for vote in game_record.votes:
            if role_by_player.get(vote.voter) != "citizen":
                continue
            stats = stats_by_player.setdefault(vote.voter, PlayerStats(player_name=vote.voter))
            stats.citizen_vote_total += 1
            if vote.vote_target in wolf_players:
                stats.citizen_vote_hits += 1

    for stats in stats_by_player.values():
        if stats.citizen_games:
            stats.citizen_win_rate = stats.citizen_wins / stats.citizen_games
        if stats.wolf_games:
            stats.wolf_win_rate = stats.wolf_wins / stats.wolf_games
        if stats.citizen_vote_total:
            stats.citizen_vote_hit_rate = stats.citizen_vote_hits / stats.citizen_vote_total

    return sorted(stats_by_player.values(), key=lambda item: item.player_name)


def print_game_header(game_number: int, total_games: int) -> None:
    if total_games <= 1:
        return
    print(f"\n{'#' * 50}")
    print(f"  GAME {game_number}/{total_games}")
    print(f"{'#' * 50}")


def format_rate(value: float) -> str:
    return f"{value * 100:.1f}%"


def format_count_or_na(value: int, available: bool) -> str:
    return str(value) if available else "n/a"


def format_wins_or_na(wins: int, rate: float, games: int) -> str:
    if not games:
        return "n/a"
    return f"{wins} ({format_rate(rate)})"


def print_player_stats(player_stats: list[PlayerStats]) -> None:
    print(f"\n{'=' * 50}")
    print("  PLAYER STATISTICS")
    print(f"{'=' * 50}")
    for stats in player_stats:
        has_citizen_games = stats.citizen_games > 0
        has_wolf_games = stats.wolf_games > 0
        was_eliminated_as_wolf = stats.eliminated_as_wolf_games > 0

        print(f"\n  {stats.player_name}")
        print(f"    citizen games: {stats.citizen_games}")
        print(f"    wolf games: {stats.wolf_games}")
        print(f"    total wins: {stats.total_wins}")
        print(f"    citizen wins: {format_wins_or_na(stats.citizen_wins, stats.citizen_win_rate, stats.citizen_games)}")
        print(f"    wolf wins: {format_wins_or_na(stats.wolf_wins, stats.wolf_win_rate, stats.wolf_games)}")
        print(f"    eliminated: {stats.eliminated_games}")
        print(f"    eliminated as wolf: {format_count_or_na(stats.eliminated_as_wolf_games, has_wolf_games)}")
        print(
            "    wolf guess successes after elimination: "
            f"{format_count_or_na(stats.wolf_guess_successes, was_eliminated_as_wolf)}"
        )
        if has_citizen_games and stats.citizen_vote_total:
            print(
                "    citizen vote accuracy: "
                f"{stats.citizen_vote_hits}/{stats.citizen_vote_total} ({format_rate(stats.citizen_vote_hit_rate)})"
            )
        else:
            print("    citizen vote accuracy: n/a")


async def main():
    parser = build_parser()
    args = parser.parse_args()
    os.environ["BAML_LOG"] = "info" if args.prompt_debug else "warn"
    num_players, num_rounds, model_list, wolf_indices, word_pair = validate_args(parser, args)

    # --continue mode: load state from JSON and override args
    continue_state: ContinueState | None = None
    if args.continue_json:
        continue_state = load_continue_state(args.continue_json)
        num_players = continue_state.num_players
        num_rounds = continue_state.num_rounds
        model_list = continue_state.model_list
        args.json = True
        args.reflection = continue_state.run_reflection
        args.no_advice = not continue_state.show_advice
        args.lang = continue_state.language
        args.wolves = continue_state.num_wolves
        if args.game_id is None:
            args.game_id = continue_state.game_id

    if args.seed is not None:
        random.seed(args.seed)

    event_handler = CLIEventHandler()
    input_provider = CLIInputProvider() if args.human else None
    human_name = input_provider.get_player_name() if input_provider else None

    prior_lessons_by_player: dict[str, str] = {}
    lessons_history: dict[str, list[PlayerLessonsHistoryEntry]] = {}
    game_records: list[GameRecord] = []
    used_word_pairs: set[frozenset[str]] = set()
    prior_games_count = 0

    if continue_state:
        prior_lessons_by_player = continue_state.prior_lessons_by_player
        lessons_history = continue_state.lessons_history
        game_records = continue_state.prior_game_records
        used_word_pairs = continue_state.used_word_pairs
        prior_games_count = len(continue_state.prior_game_records)

    replay_timestamp = None
    output_dir = args.output_dir or "../replay"
    if args.json or args.html:
        replay_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    started_at = continue_state.started_at if continue_state else datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    total_games = prior_games_count + args.games
    uses_random_word_pairs = (
        not args.generate_word_pair
        and word_pair is None
        and (args.word_pair_index is None if not continue_state else True)
    )

    for game_number in range(prior_games_count + 1, total_games + 1):
        print_game_header(game_number, total_games)

        # Pick a unique word pair for this game if using random selection
        game_word_pair = word_pair
        if uses_random_word_pairs and total_games >= 2:
            w1, w2 = pick_unique_word_pair(used_word_pairs)
            game_word_pair = (w1, w2)

        config = make_config(
            args,
            num_players,
            num_rounds,
            model_list,
            wolf_indices,
            game_word_pair,
            human_name,
            prior_lessons_by_player if total_games >= 2 and args.reflection else {},
        )
        engine = GameEngine(config, event_handler=event_handler, input_provider=input_provider)
        game_record = await engine.run()
        game_record.game_id = args.game_id
        game_records.append(game_record)

        # Track used word pairs
        used_word_pairs.add(frozenset((game_record.citizen_word, game_record.wolf_word)))

        if total_games >= 2 and args.reflection:
            update_lessons_history(game_number, game_record, prior_lessons_by_player, lessons_history)

        if args.html:
            html_content = render_html(game_record)
            html_filename = build_replay_filename(
                replay_timestamp,
                "html",
                output_dir,
                game_number if total_games >= 2 else None,
            )
            output_artifact("HTML", html_content, html_filename)

    completed_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    if total_games >= 2:
        player_stats = build_player_stats(game_records)
        print_player_stats(player_stats)
    else:
        player_stats = []

    if args.json:
        if total_games == 1:
            json_content = game_record_json(game_records[0])
        else:
            multi_game_record = MultiGameRecord(
                games=game_records,
                player_stats=player_stats,
                lessons_history=lessons_history if args.reflection else {},
                game_id=args.game_id,
                seed=args.seed,
                games_count=total_games,
                started_at=started_at,
                completed_at=completed_at,
            )
            json_content = multi_game_record_json(multi_game_record)
        json_filename = build_replay_filename(replay_timestamp, "json", output_dir)
        output_artifact("JSON", json_content, json_filename)


if __name__ == "__main__":
    asyncio.run(main())
