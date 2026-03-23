[日本語](./README-ja.md)

# Word Wolf — LLM Multi-Agent Game

An experimental project where LLM agents play **Word Wolf**, a social deduction game similar to Werewolf. By default all gameplay is driven by LLMs, but you can join the game yourself.

## What is Word Wolf?

Word Wolf is a word-based social deduction game:

- Each player is secretly given a word. Most players (citizens) share the same word; a minority (wolves) share a different, closely related word.
- No one knows their own role. Players must infer whether they are a citizen or a wolf from how others discuss their word.
- Players discuss by hinting at their word without saying it directly.
- After discussion, everyone votes to eliminate the most suspicious player.
- If a wolf is eliminated, that wolf gets one last chance to guess the citizens' word. A correct guess means the wolves win.

## Features

- **Fully autonomous gameplay**: Up to 10 LLM agents play from start to finish
- **Human player mode**: Join the game yourself with `--human` and play alongside LLM agents
- **Web UI**: Browser-based interface for watching or joining games (`web_app.py`)
- **Multi-model support**: Assign different LLM models to each player for cross-model comparison
- **Experiment control**: Deterministic seeds, fixed wolf assignments, and word pair selection for reproducible experiments
- **Configurable**: Number of players, wolves, rounds, and discussion language
- **Replay output**: Save full game records as JSON or HTML
- **Batch CLI runs**: Run multiple games in sequence with `--games` and collect per-player statistics

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv)
- OpenRouter API key

## Setup

```bash
cd src
uv sync
uv run baml-cli generate
export OPENROUTER_KEY=[your_openrouter_api_key]
```

## Usage

### CLI

Run from the `src` directory:

```bash
uv run python main.py [options]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--players N` | `3` | Number of players (3–10) |
| `--wolves N` | `1` | Number of wolves (1 to floor(players/2)) |
| `--rounds N` | `2` | Number of discussion rounds |
| `--games N` | `1` | Number of games to run in sequence (CLI only) |
| `--lang LANG` | English | Language for discussion (e.g. `Japanese`, `French`) |
| `--models m1,m2,...` | (default client) | Comma-separated OpenRouter model IDs; one per player, or a single model for all players |
| `--reflection` | off | Run post-game reflection phase (each agent reflects on their play) |
| `--human` | off | Join the game as a human player (cannot be used with `--wolf-indices`) |
| `--html` | off | Save HTML replay output |

### Advanced Options

Options primarily intended for LLM experiments and research.

| Flag | Default | Description |
|------|---------|-------------|
| `--hide-thinking` | off | Hide each agent's private reasoning |
| `--no-advice` | off | Hide strategy advice from the discussion prompt (see below) |
| `--json` | off | Save replay JSON |
| `--wolf-indices 0,2` | random | Comma-separated wolf player indices (0-based) |
| `--word-pair-index N` | random | Index into the word pair list (0-based) |
| `--word-pair W1 W2` | none | Specify citizen word and wolf word directly (skips random selection; cannot be used with `--word-pair-index`) |
| `--generate-word-pair` | off | Generate a novel word pair via LLM instead of selecting from the predefined list (cannot be used with `--word-pair` or `--word-pair-index`) |
| `--seed N` | none | Random seed for reproducible speaker order and tiebreaks |
| `--game-id ID` | none | Experiment identifier included in JSON output |
| `--output-dir DIR` | `../replay` | Output directory for replay files |
| `--continue JSON_FILE` | none | Continue from a previously saved JSON file (requires `--games`; see below) |
| `--prompt-debug` | off | Enable prompt debug logging |

### Multi-game CLI runs

`--games N` is supported only in the CLI. The web UI remains single-game.

- When `--games >= 2`, the CLI runs `N` games back to back and prints per-player statistics at the end.
- When `--games >= 2 --reflection` is used, each player's `lessons_learned` is carried into the next game and refined after every round of play.
- When word pairs are randomly selected (no `--word-pair`, `--word-pair-index`, or `--generate-word-pair`), each game in the batch uses a different word pair. Once all predefined pairs are exhausted, the full set becomes available again.

#### `--continue` option

Use `--continue` to extend a completed experiment by loading a previously saved JSON file and running additional games. All game settings (players, wolves, rounds, models, language, etc.), lessons learned, and used word pairs are inherited from the JSON.

```bash
# Run 5 initial games
uv run python main.py --games 5 --reflection --json

# Continue with 5 more games from the saved JSON
uv run python main.py --continue ../replay/wordwolf_replay_20250101_120000.json --games 5
```

- `--games N` is required with `--continue`
- `--json` is implied (the combined result is always saved as JSON)
- Game numbering, player statistics, and lessons learned continue from where the previous run left off
- Word pairs used in previous games are excluded from random selection
- Settings like `--players`, `--wolves`, `--rounds`, `--models`, `--reflection` cannot be overridden — they are inherited from the JSON
- Both single-game and multi-game JSON files are supported as input

#### `--no-advice` option

By default, the discussion prompt includes a **"How to speak"** section that gives each agent explicit strategic guidance, for example, how to infer whether you are a citizen or wolf from others' hints, how to deflect suspicion, and when to probe other players with questions.

Using `--no-advice` removes this section entirely. Agents are only told the basic rules of the game and must figure out their own strategy from scratch. This is useful for measuring the raw strategic reasoning capability of the LLM without the scaffolding of pre-written heuristics.

```bash
# Measure strategic reasoning without built-in advice
uv run python main.py --no-advice
```

### Examples

```bash
# Quick 3-player game (default)
uv run python main.py

# Run 10 games in sequence and print per-player stats
uv run python main.py --games 10

# Play as a human against LLM agents
uv run python main.py --human --players 5

# 6 players, 2 wolves, 3 discussion rounds
uv run python main.py --players 6 --wolves 2 --rounds 3

# Play in Japanese, save HTML replay
uv run python main.py --players 5 --lang Japanese --html

# Multi-game run with evolving reflections and aggregated JSON
uv run python main.py --games 5 --reflection --json --html

# Continue a previous run with 3 more games
uv run python main.py --continue ../replay/wordwolf_replay_20250101_120000.json --games 3

# Hide agent reasoning
uv run python main.py --hide-thinking

# Single model for all players
uv run python main.py --models "anthropic/claude-opus-4.6" --players 5

# Multi-model experiment: 3 different models, player 0 is wolf, fixed word pair and seed
uv run python main.py \
  --models "openai/gpt-5.4,anthropic/claude-opus-4.6,google/gemini-3.1-pro-preview" \
  --wolf-indices 0 \
  --word-pair-index 5 \
  --seed 42 \
  --game-id "block1_game1" \
  --json --output-dir ../results
```

### Web UI

Run from the `src` directory:

```bash
uv run python web_app.py
```

Open `http://localhost:5000` in your browser. The web UI lets you watch AI play or join as a human player. Word pairs are generated by LLM each game.


## Multi-Model Experiments

You can pit different LLM models against each other by assigning one model per player with `--models`. Combined with `--wolf-indices`, `--word-pair-index`, and `--seed`, this enables fully controlled experiments to compare model capabilities in social deduction.

The `--game-id` and `--seed` fields are included in the JSON output for experiment tracking. With `--games >= 2`, the seed is applied once at the start of the batch so the entire sequence is reproducible.

## Project Structure

```
src/
├── main.py              # CLI entry point (argparse, CLIEventHandler, CLIInputProvider)
├── engine.py            # GameEngine class, protocols (GameEventHandler, InputProvider), core game logic
├── models.py            # Dataclasses (GameConfig, GameRecord, etc.) and constants
├── rendering.py         # HTML/JSON rendering and file output
├── word_pairs.py        # Word pairs used for citizen/wolf words
├── templates/
│   └── game_report.html # HTML replay template
└── baml_src/
    ├── clients.baml     # LLM client definitions (OpenRouter)
    ├── types.baml       # BAML data types
    └── game.baml        # Prompts: Discuss, Vote, GuessWord, JudgeGuess, Reflect
```

`src/baml_client/` is auto-generated — do not edit directly. After modifying any `.baml` file, regenerate with:

```bash
cd src
uv run baml-cli generate
```

## Customization

| What to change | Where to edit |
|----------------|---------------|
| Word pairs used in the game | `src/word_pairs.py` |
| Player names | Constants in `src/models.py` |
| LLM model | `src/baml_src/clients.baml` |
| LLM prompts | `src/baml_src/game.baml` |

After editing any `.baml` file, regenerate the client:

```bash
cd src
uv run baml-cli generate
```

## Credits

Word Wolf was designed by **Susumu Kawasaki**. This experimental program was inspired by his work.
