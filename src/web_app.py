import argparse
import asyncio
from datetime import datetime
import os
import queue
import random
import string
import sys
import threading
import uuid
from dataclasses import dataclass, field

from flask import Flask, Response, redirect, render_template, request, session, url_for

from models import GameConfig
from engine import GameEngine
from web_handlers import WebEventHandler, WebInputProvider
from rendering import render_html, output_artifact, build_replay_filename

os.environ.setdefault("BAML_LOG", "warn")

if not os.environ.get("OPENROUTER_KEY"):
    print("Error: OPENROUTER_KEY environment variable is not set.", file=sys.stderr)
    sys.exit(1)

parser = argparse.ArgumentParser(description="Word Wolf Web UI")
parser.add_argument("--model", type=str, default=None, help="OpenRouter model ID to use for all players")
_args, _ = parser.parse_known_args()
DEFAULT_MODEL: str | None = _args.model

app = Flask(__name__)
app.secret_key = uuid.uuid4().hex

ACCESS_CODE = "".join(random.choices(string.ascii_uppercase, k=6))
print(f"Access code: {ACCESS_CODE}", flush=True)
if DEFAULT_MODEL:
    print(f"Model: {DEFAULT_MODEL}", flush=True)


@dataclass
class GameSession:
    game_id: str
    event_queue: queue.Queue
    input_provider: WebInputProvider | None = None
    thread: threading.Thread | None = None
    config: dict = field(default_factory=dict)
    status: str = "running"


sessions: dict[str, GameSession] = {}


def _run_game(session: GameSession, config: GameConfig, event_handler: WebEventHandler, input_provider: WebInputProvider | None):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        engine = GameEngine(config, event_handler=event_handler, input_provider=input_provider)
        game_record = loop.run_until_complete(engine.run())
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        html_content = render_html(game_record)
        html_filename = build_replay_filename(timestamp, "html")
        output_artifact("HTML", html_content, html_filename)
        session.event_queue.put('{"type": "game_end"}')
        session.status = "finished"
    except Exception as e:
        session.event_queue.put(f'{{"type": "error", "message": {repr(str(e))}}}')
        session.status = "error"
    finally:
        loop.close()


@app.route("/")
def index():
    if not session.get("authenticated"):
        return render_template("web_game.html", page="auth")
    return render_template("web_game.html", page="setup")


@app.route("/auth", methods=["POST"])
def auth():
    code = request.form.get("code", "").strip().upper()
    if code == ACCESS_CODE:
        session["authenticated"] = True
        return redirect(url_for("index"))
    return render_template("web_game.html", page="auth", error="Invalid access code.")


@app.route("/start", methods=["POST"])
def start():
    if not session.get("authenticated"):
        return redirect(url_for("index"))
    game_id = uuid.uuid4().hex[:12]
    eq = queue.Queue()

    mode = request.form.get("mode", "spectator")
    num_players = int(request.form.get("num_players", 3))
    num_wolves = int(request.form.get("num_wolves", 1))
    num_rounds = int(request.form.get("num_rounds", 2))
    language = request.form.get("language", "").strip() or None
    show_thinking = request.form.get("show_thinking") == "on"
    run_reflection = request.form.get("run_reflection") == "on"

    is_human = mode == "human"
    human_name = "__human__" if is_human else None
    lang = "ja" if language == "japanese" else "en"

    clamped_num_players = max(3, min(10, num_players))
    clamped_num_wolves = max(1, min((clamped_num_players - 1) // 2, num_wolves))
    model_list = [DEFAULT_MODEL] * clamped_num_players if DEFAULT_MODEL else None

    config = GameConfig(
        num_players=clamped_num_players,
        num_wolves=clamped_num_wolves,
        num_rounds=max(1, min(5, num_rounds)),
        language=language,
        show_thinking=show_thinking if not is_human else False,
        human_name=human_name,
        generate_word_pair=True,
        run_reflection=run_reflection,
        model_list=model_list,
    )

    event_handler = WebEventHandler(eq)
    input_provider = WebInputProvider(eq) if is_human else None

    game_session = GameSession(
        game_id=game_id,
        event_queue=eq,
        input_provider=input_provider,
        config={"mode": mode, "num_players": config.num_players, "num_rounds": config.num_rounds, "lang": lang},
    )
    sessions[game_id] = game_session

    thread = threading.Thread(target=_run_game, args=(game_session, config, event_handler, input_provider), daemon=True)
    game_session.thread = thread
    thread.start()

    return redirect(url_for("game", game_id=game_id))


@app.route("/game/<game_id>")
def game(game_id: str):
    session = sessions.get(game_id)
    if not session:
        return redirect(url_for("index"))
    lang = session.config.get("lang", "en")
    return render_template("web_game.html", page="game", game_id=game_id, lang=lang)


@app.route("/stream/<game_id>")
def stream(game_id: str):
    session = sessions.get(game_id)
    if not session:
        return Response("Game not found", status=404)

    def generate():
        while True:
            try:
                data = session.event_queue.get(timeout=30)
                yield f"data: {data}\n\n"
                if '"type": "game_end"' in data or '"type": "error"' in data:
                    break
            except queue.Empty:
                yield ": keepalive\n\n"

    return Response(generate(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


@app.route("/input/<game_id>", methods=["POST"])
def submit_input(game_id: str):
    session = sessions.get(game_id)
    if not session or not session.input_provider:
        return {"error": "Invalid session"}, 400
    data = request.get_json(force=True)
    value = data.get("value", "").strip()
    if not value:
        return {"error": "Empty input"}, 400
    session.input_provider.submit(value)
    return {"ok": True}


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000, threaded=True)
