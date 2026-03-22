import json
import sys
from pathlib import Path

from rendering import output_artifact, parse_game_record, render_html


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <json_file>", file=sys.stderr)
        sys.exit(1)

    json_path = Path(sys.argv[1])
    if not json_path.is_file():
        print(f"File not found: {json_path}", file=sys.stderr)
        sys.exit(1)

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    is_multi = "games" in data
    game_dicts = data["games"] if is_multi else [data]

    stem = json_path.stem
    parent = json_path.parent

    for i, game_dict in enumerate(game_dicts, start=1):
        record = parse_game_record(game_dict)
        html_content = render_html(record)
        if is_multi:
            html_path = parent / f"{stem}_game{i:02d}.html"
        else:
            html_path = parent / f"{stem}.html"
        output_artifact("HTML", html_content, str(html_path))


if __name__ == "__main__":
    main()
