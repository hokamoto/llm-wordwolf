import json
import queue
import threading


class WebEventHandler:
    """GameEventHandler implementation that serializes events to a queue for SSE."""

    def __init__(self, event_queue: queue.Queue):
        self._queue = event_queue

    def _push(self, data: dict):
        self._queue.put(json.dumps(data, ensure_ascii=False))

    def on_game_start(self, players, citizen_word, wolf_word, num_rounds, human_name, model_map=None):
        self._push({
            "type": "game_start",
            "players": [{"name": p["name"], "role": p["role"], "word": p["word"]} for p in players],
            "citizen_word": citizen_word,
            "wolf_word": wolf_word,
            "num_rounds": num_rounds,
            "human_name": human_name,
        })

    def on_discussion_start(self):
        self._push({"type": "discussion_start"})

    def on_discussion_turn(self, speaker_name, thinking, statement, show_thinking):
        self._push({
            "type": "discussion_turn",
            "speaker": speaker_name,
            "thinking": thinking if show_thinking else None,
            "statement": statement,
        })

    def on_human_discussion_prompt(self, speaker_name, word, round_num, total_rounds):
        self._push({
            "type": "input_needed",
            "input_type": "discussion",
            "speaker": speaker_name,
            "word": word,
            "round_num": round_num,
            "total_rounds": total_rounds,
        })

    def on_voting_start(self):
        self._push({"type": "voting_start"})

    def on_vote_cast(self, voter_display, thinking, vote_target_display, show_thinking, used_random_fallback):
        self._push({
            "type": "vote_cast",
            "voter": voter_display,
            "thinking": thinking if show_thinking else None,
            "target": vote_target_display,
            "used_random_fallback": used_random_fallback,
        })

    def on_vote_tally(self, tally, display_names):
        self._push({
            "type": "vote_tally",
            "tally": {display_names.get(k, k): v for k, v in tally.items()},
        })

    def on_resolution_start(self):
        self._push({"type": "resolution_start"})

    def on_elimination(self, eliminated_display, role):
        self._push({
            "type": "elimination",
            "eliminated": eliminated_display,
            "role": role,
        })

    def on_wolf_found(self):
        self._push({"type": "wolf_found"})

    def on_wolf_guess(self, eliminated_display, guess_text, citizen_word, guess_thinking, show_thinking):
        self._push({
            "type": "wolf_guess",
            "eliminated": eliminated_display,
            "guess": guess_text,
            "citizen_word": citizen_word,
            "thinking": guess_thinking if show_thinking else None,
        })

    def on_judge_result(self, is_correct, show_thinking):
        self._push({
            "type": "judge_result",
            "is_correct": is_correct,
        })

    def on_game_result(self, summary, winner):
        self._push({"type": "game_result", "summary": summary, "winner": winner})

    def on_citizen_eliminated(self, summary):
        self._push({"type": "citizen_eliminated", "summary": summary})

    def on_reflection_start(self):
        self._push({"type": "reflection_start"})

    def on_reflection(self, speaker_name, reflection, lessons_learned):
        self._push({
            "type": "reflection",
            "speaker": speaker_name,
            "reflection": reflection,
            "lessons_learned": lessons_learned,
        })

    def on_game_reveal(self, citizen_word, wolf_word, players):
        self._push({
            "type": "game_reveal",
            "citizen_word": citizen_word,
            "wolf_word": wolf_word,
            "players": [{"name": p["name"], "role": p["role"], "word": p["word"]} for p in players],
        })

    def on_generate_word_pair(self):
        self._push({"type": "generate_word_pair"})


class WebInputProvider:
    """InputProvider implementation that blocks on a threading.Event until browser submits input."""

    def __init__(self, event_queue: queue.Queue):
        self._queue = event_queue
        self._event = threading.Event()
        self._value: str = ""

    def _push(self, data: dict):
        self._queue.put(json.dumps(data, ensure_ascii=False))

    def _wait_for_input(self) -> str:
        self._event.clear()
        self._event.wait()
        return self._value

    def submit(self, value: str):
        self._value = value
        self._event.set()

    def get_player_name(self) -> str:
        self._push({"type": "input_needed", "input_type": "player_name"})
        return self._wait_for_input()

    def get_discussion_input(self, player_name: str, word: str, round_num: int, total_rounds: int) -> str:
        return self._wait_for_input()

    def get_vote_input(self, player_name: str, candidates: list[str]) -> str:
        self._push({
            "type": "input_needed",
            "input_type": "vote",
            "candidates": candidates,
        })
        return self._wait_for_input()

    def get_wolf_guess_input(self, player_name: str) -> str:
        self._push({
            "type": "input_needed",
            "input_type": "wolf_guess",
        })
        return self._wait_for_input()
