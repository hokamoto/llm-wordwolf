import asyncio
from collections import Counter
from datetime import datetime
import os
import random
from typing import Any, Protocol

from baml_py.baml_py import BamlError

from models import (
    PLAYER_NAMES,
    GameConfig,
    GameRecord,
    PlayerRecord,
    DiscussionTurn,
    VoteRecord,
    ResolutionRecord,
    ReflectionRecord,
    build_display_name_map,
    display_name,
    normalize_prompt_language,
)
from word_pairs import WORD_PAIRS


async def call_with_retry(fn, **kwargs):
    try:
        return await fn(**kwargs)
    except BamlError:
        return await fn(**{**kwargs, "is_retry": True})


b = None


def get_baml_client():
    global b
    if b is None:
        from baml_client import b as baml_client_instance

        b = baml_client_instance
    return b


def build_player_clients(players: list[dict], model_list: list[str] | None = None) -> dict:
    """Return {player_name: BamlAsyncClient} with per-player model."""
    import baml_py

    baml_client = get_baml_client()
    if not model_list:
        return {p["name"]: baml_client for p in players}
    clients = {}
    for i, player in enumerate(players):
        model_id = model_list[i]
        cr = baml_py.ClientRegistry()
        cr.add_llm_client(
            name="LLMInstance",
            provider="openai-generic",
            options={
                "base_url": "https://openrouter.ai/api/v1",
                "api_key": os.environ.get("OPENROUTER_KEY", ""),
                "model": model_id,
            },
        )
        cr.set_primary("LLMInstance")
        clients[player["name"]] = baml_client.with_options(client_registry=cr)
    return clients


def build_annotated_history(discussion: list[DiscussionTurn], player_name: str) -> list[Any]:
    from baml_client.types import AnnotatedMessage

    return [
        AnnotatedMessage(
            speaker=turn.speaker,
            thinking=turn.thinking if turn.speaker == player_name else None,
            content=turn.statement,
        )
        for turn in discussion
    ]



def setup_game(
    num_players: int,
    num_wolves: int,
    wolf_indices: list[int] | None = None,
    word_pair_index: int | None = None,
    word_pair: tuple[str, str] | None = None,
) -> tuple[list[dict], str, str]:
    names = PLAYER_NAMES[:num_players]
    if word_pair is not None:
        citizen_word, wolf_word = word_pair
    elif word_pair_index is not None:
        word_a, word_b = WORD_PAIRS[word_pair_index]
        citizen_word, wolf_word = random.sample([word_a, word_b], k=2)
    else:
        word_a, word_b = random.choice(WORD_PAIRS)
        citizen_word, wolf_word = random.sample([word_a, word_b], k=2)
    if wolf_indices is not None:
        wolf_idx_set = set(wolf_indices)
    else:
        wolf_idx_set = set(random.sample(range(num_players), k=num_wolves))

    players = []
    for i, name in enumerate(names):
        if i in wolf_idx_set:
            players.append({"name": name, "word": wolf_word, "role": "wolf"})
        else:
            players.append({"name": name, "word": citizen_word, "role": "citizen"})

    return players, citizen_word, wolf_word


def build_game_record(
    players: list[dict],
    citizen_word: str,
    wolf_word: str,
    rounds: int,
    model_map: dict[str, str] | None = None,
    game_id: str | None = None,
    seed: int | None = None,
) -> GameRecord:
    return GameRecord(
        players=[
            PlayerRecord(
                name=p["name"],
                role=p["role"],
                word=p["word"],
                model=model_map.get(p["name"]) if model_map else None,
            )
            for p in players
        ],
        wolf_count=sum(1 for p in players if p["role"] == "wolf"),
        citizen_word=citizen_word,
        wolf_word=wolf_word,
        rounds=rounds,
        discussion=[],
        votes=[],
        tally={},
        game_id=game_id,
        seed=seed,
    )


class GameEventHandler(Protocol):
    def on_game_start(self, players: list[dict], citizen_word: str, wolf_word: str, num_rounds: int, human_name: str | None, model_map: dict[str, str] | None) -> None: ...
    def on_discussion_start(self) -> None: ...
    def on_discussion_turn(self, speaker_name: str, thinking: str | None, statement: str, show_thinking: bool) -> None: ...
    def on_human_discussion_prompt(self, speaker_name: str, word: str, round_num: int, total_rounds: int) -> None: ...
    def on_voting_start(self) -> None: ...
    def on_vote_cast(self, voter_display: str, thinking: str | None, vote_target_display: str, show_thinking: bool, used_random_fallback: bool) -> None: ...
    def on_vote_tally(self, tally: dict[str, int], display_names: dict[str, str]) -> None: ...
    def on_resolution_start(self) -> None: ...
    def on_elimination(self, eliminated_display: str, role: str) -> None: ...
    def on_wolf_found(self) -> None: ...
    def on_wolf_guess(self, eliminated_display: str, guess_text: str, citizen_word: str, guess_thinking: str | None, show_thinking: bool) -> None: ...
    def on_judge_result(self, is_correct: bool, show_thinking: bool) -> None: ...
    def on_game_result(self, summary: str, winner: str) -> None: ...
    def on_citizen_eliminated(self, summary: str) -> None: ...
    def on_reflection_start(self) -> None: ...
    def on_reflection(self, speaker_name: str, reflection: str, lessons_learned: str | None) -> None: ...
    def on_game_reveal(self, citizen_word: str, wolf_word: str, players: list[dict]) -> None: ...
    def on_generate_word_pair(self) -> None: ...


class NullEventHandler:
    def on_game_start(self, players, citizen_word, wolf_word, num_rounds, human_name, model_map=None): pass
    def on_discussion_start(self): pass
    def on_discussion_turn(self, speaker_name, thinking, statement, show_thinking): pass
    def on_human_discussion_prompt(self, speaker_name, word, round_num, total_rounds): pass
    def on_voting_start(self): pass
    def on_vote_cast(self, voter_display, thinking, vote_target_display, show_thinking, used_random_fallback): pass
    def on_vote_tally(self, tally, display_names): pass
    def on_resolution_start(self): pass
    def on_elimination(self, eliminated_display, role): pass
    def on_wolf_found(self): pass
    def on_wolf_guess(self, eliminated_display, guess_text, citizen_word, guess_thinking, show_thinking): pass
    def on_judge_result(self, is_correct, show_thinking): pass
    def on_game_result(self, summary, winner): pass
    def on_citizen_eliminated(self, summary): pass
    def on_reflection_start(self): pass
    def on_reflection(self, speaker_name, reflection, lessons_learned): pass
    def on_game_reveal(self, citizen_word, wolf_word, players): pass
    def on_generate_word_pair(self): pass


class InputProvider(Protocol):
    def get_discussion_input(self, player_name: str, word: str, round_num: int, total_rounds: int) -> str: ...
    def get_vote_input(self, player_name: str, candidates: list[str]) -> str: ...
    def get_wolf_guess_input(self, player_name: str) -> str: ...
    def get_player_name(self) -> str: ...


class GameEngine:
    def __init__(
        self,
        config: GameConfig,
        event_handler: GameEventHandler | None = None,
        input_provider: InputProvider | None = None,
    ):
        self.config = config
        self.events: GameEventHandler = event_handler or NullEventHandler()
        self.input_provider = input_provider
        self._players: list[dict] = []
        self._citizen_word: str = ""
        self._wolf_word: str = ""
        self._player_clients: dict = {}
        self._game_record: GameRecord | None = None

    async def run(self) -> GameRecord:
        await self._setup()
        await self._discussion_phase()
        eliminated = await self._voting_phase()
        await self._resolution_phase(eliminated)
        if self.config.human_name:
            self.events.on_game_reveal(self._citizen_word, self._wolf_word, self._players)
        if self.config.run_reflection:
            await self._reflection_phase()
        return self._game_record

    async def _setup(self) -> None:
        config = self.config

        if config.human_name == "__human__" and self.input_provider:
            human_name = self.input_provider.get_player_name()
            config.human_name = human_name
        else:
            human_name = config.human_name

        word_pair = config.word_pair

        if config.generate_word_pair:
            self.events.on_generate_word_pair()
            baml_client = get_baml_client()
            result = await baml_client.GenerateWordPair()
            word_pair = tuple(random.sample([result.word1.lower(), result.word2.lower()], 2))

        self._players, self._citizen_word, self._wolf_word = setup_game(
            config.num_players, config.num_wolves, config.wolf_indices,
            config.word_pair_index, word_pair,
        )

        if human_name:
            slot = random.randint(0, config.num_players - 1)
            self._players[slot]["name"] = human_name

        model_map = None
        if config.model_list:
            model_map = {self._players[i]["name"]: config.model_list[i] for i in range(config.num_players)}

        self._player_clients = build_player_clients(self._players, config.model_list)
        if config.human_name:
            self._player_clients[config.human_name] = None

        self._game_record = build_game_record(
            self._players, self._citizen_word, self._wolf_word,
            config.num_rounds, model_map, config.game_id, config.seed,
        )

        self._game_record.timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        self._game_record.language = config.language
        self._game_record.show_advice = config.show_advice

        self.events.on_game_start(
            self._players, self._citizen_word, self._wolf_word,
            config.num_rounds, config.human_name, model_map,
        )

    async def _discussion_phase(self) -> None:
        config = self.config
        players = self._players
        game_record = self._game_record
        player_names = [p["name"] for p in players]
        prompt_language = normalize_prompt_language(config.language)

        self.events.on_discussion_start()
        last_speaker = None
        for round_num in range(1, config.num_rounds + 1):
            order = list(players)
            random.shuffle(order)
            if last_speaker is not None and len(order) > 1 and order[0]["name"] == last_speaker:
                order[0], order[1] = order[1], order[0]
            last_speaker = order[-1]["name"]

            for player in order:
                speaker_name = player["name"] if config.human_name else display_name(player)

                if player["name"] == config.human_name:
                    self.events.on_human_discussion_prompt(
                        speaker_name, player["word"], round_num, config.num_rounds,
                    )
                    statement = self.input_provider.get_discussion_input(
                        player["name"], player["word"], round_num, config.num_rounds,
                    )
                    game_record.discussion.append(
                        DiscussionTurn(
                            round_number=round_num,
                            speaker=player["name"],
                            thinking=None,
                            statement=statement,
                        )
                    )
                    self.events.on_discussion_turn(speaker_name, None, statement, False)
                    continue

                response = await call_with_retry(
                    self._player_clients[player["name"]].Discuss,
                    player_name=player["name"],
                    player_word=player["word"],
                    player_names=player_names,
                    wolf_count=game_record.wolf_count,
                    discussion_history=build_annotated_history(game_record.discussion, player["name"]),
                    round_number=round_num,
                    total_rounds=config.num_rounds,
                    prior_lessons_learned=config.prior_lessons_by_player.get(player["name"]),
                    language=prompt_language,
                    show_advice=config.show_advice,
                )
                self.events.on_discussion_turn(speaker_name, response.thinking, response.statement, config.show_thinking)

                game_record.discussion.append(
                    DiscussionTurn(
                        round_number=round_num,
                        speaker=player["name"],
                        thinking=response.thinking,
                        statement=response.statement,
                    )
                )

    async def _voting_phase(self) -> dict:
        config = self.config
        players = self._players
        game_record = self._game_record
        player_names = [p["name"] for p in players]
        display_names = build_display_name_map(players)
        if config.human_name:
            display_names = {p["name"]: p["name"] for p in players}
        votes: dict[str, str] = {}
        prompt_language = normalize_prompt_language(config.language)

        self.events.on_voting_start()

        async def vote_one(player: dict) -> VoteRecord:
            error_feedback = ""
            vote_target = None
            vote_thinking = ""
            attempts_used = 0

            for attempt in range(2):
                response = await call_with_retry(
                    self._player_clients[player["name"]].Vote,
                    player_name=player["name"],
                    player_word=player["word"],
                    player_names=player_names,
                    wolf_count=game_record.wolf_count,
                    discussion_history=build_annotated_history(game_record.discussion, player["name"]),
                    error_feedback=error_feedback,
                    language=prompt_language,
                    show_advice=config.show_advice,
                )
                attempts_used = attempt + 1
                vote_thinking = response.thinking

                target = response.vote.strip()
                if target not in player_names:
                    error_feedback = f"'{target}' is not a valid player name. Choose from: {', '.join(n for n in player_names if n != player['name'])}"
                    continue

                vote_target = target
                break

            used_random_fallback = False
            if vote_target is None:
                others = [n for n in player_names if n != player["name"]]
                vote_target = random.choice(others)
                used_random_fallback = True

            return VoteRecord(
                voter=player["name"],
                thinking=vote_thinking,
                vote_target=vote_target,
                attempts=attempts_used,
                used_random_fallback=used_random_fallback,
            )

        def human_vote(player: dict) -> VoteRecord:
            others = [n for n in player_names if n != player["name"]]
            choice = self.input_provider.get_vote_input(player["name"], others)
            return VoteRecord(
                voter=player["name"],
                thinking=None,
                vote_target=choice,
                attempts=1,
                used_random_fallback=False,
            )

        llm_players = [p for p in players if p["name"] != config.human_name]
        human_player = next((p for p in players if p["name"] == config.human_name), None)

        llm_results = await asyncio.gather(*[vote_one(p) for p in llm_players])
        all_results = list(llm_results)
        if human_player:
            all_results.append(human_vote(human_player))

        for record in all_results:
            voter_display = display_names.get(record.voter, record.voter)
            target_display = display_names.get(record.vote_target, record.vote_target)
            self.events.on_vote_cast(
                voter_display, record.thinking, target_display,
                config.show_thinking, record.used_random_fallback,
            )
            votes[record.voter] = record.vote_target
            game_record.votes.append(record)

        tally = dict(Counter(votes.values()))
        game_record.tally = tally

        self.events.on_vote_tally(tally, display_names)

        max_votes = max(tally.values())
        candidates = [name for name, count in tally.items() if count == max_votes]
        eliminated_name = random.choice(candidates)

        return next(p for p in players if p["name"] == eliminated_name)

    async def _resolution_phase(self, eliminated: dict) -> None:
        config = self.config
        players = self._players
        game_record = self._game_record
        baml_client = get_baml_client()
        player_names = [p["name"] for p in players]
        prompt_language = normalize_prompt_language(config.language)

        self.events.on_resolution_start()
        eliminated_display = eliminated["name"] if config.human_name else display_name(eliminated)
        self.events.on_elimination(eliminated_display, eliminated["role"])

        if eliminated["role"] == "wolf":
            self.events.on_wolf_found()

            if eliminated["name"] == config.human_name:
                guess_text = self.input_provider.get_wolf_guess_input(eliminated["name"])
                guess_thinking = None
            else:
                response = await call_with_retry(
                    self._player_clients[eliminated["name"]].GuessWord,
                    player_name=eliminated["name"],
                    player_word=eliminated["word"],
                    player_names=player_names,
                    wolf_count=game_record.wolf_count,
                    discussion_history=build_annotated_history(game_record.discussion, eliminated["name"]),
                    language=prompt_language,
                )
                guess_text = response.guess
                guess_thinking = response.thinking

            self.events.on_wolf_guess(
                eliminated_display, guess_text, self._citizen_word,
                guess_thinking, config.show_thinking,
            )

            judge = await call_with_retry(baml_client.JudgeGuess, guess=guess_text, answer=self._citizen_word)
            self.events.on_judge_result(judge.is_correct, config.show_thinking)

            if judge.is_correct:
                summary = "WOLVES WIN! The eliminated wolf correctly guessed the citizen word!"
                winner = "wolves"
            else:
                summary = "CITIZENS WIN! The eliminated wolf guessed wrong."
                winner = "citizens"

            self.events.on_game_result(summary, winner)

            game_record.resolution = ResolutionRecord(
                eliminated_name=eliminated["name"],
                eliminated_role=eliminated["role"],
                wolf_guess=guess_text,
                wolf_guess_thinking=guess_thinking,
                winner=winner,
                summary=summary,
            )
        else:
            summary = "WOLVES WIN! The citizens eliminated one of their own."
            self.events.on_citizen_eliminated(summary)
            game_record.resolution = ResolutionRecord(
                eliminated_name=eliminated["name"],
                eliminated_role=eliminated["role"],
                wolf_guess=None,
                wolf_guess_thinking=None,
                winner="wolves",
                summary=summary,
            )

    async def _reflection_phase(self) -> None:
        config = self.config
        players = self._players
        game_record = self._game_record
        resolution = game_record.resolution
        from baml_client.types import VoteInfo
        prompt_language = normalize_prompt_language(config.language)

        vote_infos = [VoteInfo(voter=v.voter, vote_target=v.vote_target) for v in game_record.votes]

        self.events.on_reflection_start()

        async def reflect_one(player: dict) -> ReflectionRecord:
            from baml_client.types import AnnotatedMessage, PlayerRole
            own_turns = {
                (turn.speaker, turn.statement): turn.thinking
                for turn in game_record.discussion
                if turn.speaker == player["name"]
            }
            annotated_history = [
                AnnotatedMessage(
                    speaker=turn.speaker,
                    thinking=own_turns.get((turn.speaker, turn.statement)) if turn.speaker == player["name"] else None,
                    content=turn.statement,
                )
                for turn in game_record.discussion
            ]
            own_vote_thinking = next(
                (v.thinking for v in game_record.votes if v.voter == player["name"]),
                None,
            )
            player_roles = [PlayerRole(name=p["name"], role=p["role"]) for p in players]
            response = await call_with_retry(
                self._player_clients[player["name"]].Reflect,
                player_name=player["name"],
                player_word=player["word"],
                player_role=player["role"],
                player_names=[p["name"] for p in players],
                player_roles=player_roles,
                citizen_word=game_record.citizen_word,
                wolf_word=game_record.wolf_word,
                wolf_count=game_record.wolf_count,
                annotated_history=annotated_history,
                own_vote_thinking=own_vote_thinking,
                votes=vote_infos,
                eliminated_name=resolution.eliminated_name,
                eliminated_role=resolution.eliminated_role,
                wolf_guess=resolution.wolf_guess,
                wolf_guess_correct=(resolution.winner == "wolves" and resolution.wolf_guess is not None) if resolution.wolf_guess else None,
                winner=resolution.winner,
                prior_lessons_learned=config.prior_lessons_by_player.get(player["name"]),
                language=prompt_language,
                human_player_name=config.human_name,
                show_advice=config.show_advice,
            )
            return ReflectionRecord(
                player_name=player["name"],
                player_role=player["role"],
                reflection=response.reflection,
                lessons_learned=response.lessons_learned,
            )

        reflect_players = [p for p in players if p["name"] != config.human_name]
        results = await asyncio.gather(*[reflect_one(p) for p in reflect_players])
        for record in results:
            speaker_name = f"{record.player_name}(Wolf)" if record.player_role == "wolf" else record.player_name
            self.events.on_reflection(speaker_name, record.reflection, record.lessons_learned)
            game_record.reflections.append(record)
