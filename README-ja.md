[English](./README.md)

# ワードウルフ(Word Wolf) — LLMマルチエージェントゲーム

LLMエージェントにワードウルフをプレイさせる実験的プロジェクトです。ワードウルフはWerewolf(汝は人狼なりや?)に似た社会的推理ゲームです。デフォルトではゲームプレイはすべてLLMによって行われますが、自分でゲームに参加することもできます。

## ワードウルフとは？

ワードウルフは言葉を使った社会的推理ゲーム(social deduction game)です。

- 各プレイヤーは秘密裏に単語を与えられます。ほとんどのプレイヤー(市民)は同じ単語を共有し、少数(狼)は別の近い意味の単語を持ちます
- 誰も自分の役割を知りません。プレイヤーは他の人の言葉のヒントから、自分が市民か狼かを推理しなければなりません
- プレイヤーは単語を直接言わずにヒントを出しながら議論します
- 議論の後、全員が最も怪しいプレイヤーへ投票して排除します
- 狼が排除された場合、その狼は市民の単語を推測する最後のチャンスを得ます。正解すれば狼の勝利です

## 機能

- **完全自律型ゲームプレイ**: 最大10体のLLMエージェントが自律的に最初から最後までプレイ
- **人間プレイヤーモード**: LLMエージェントと一緒に人間がプレイ可能
- **マルチモデル対応**: 各プレイヤーに異なるLLMモデルを割り当ててモデル間比較が可能
- **リプレイ出力**: ゲーム記録をJSONまたはHTMLとして保存
- **実験制御**: 再現性のある実験のための決定論的シード、固定狼割り当て、単語ペア選択
- **カスタマイズ可能**: プレイヤー数、狼数、ラウンド数、議論言語を設定可能
- **Web UI**: ゲームを観戦または参加できるブラウザベースのインターフェース

## 必要要件

- Python 3.11以上
- [uv](https://github.com/astral-sh/uv)
- OpenRouter APIキー

## セットアップ

```bash
cd src
uv sync
uv run baml-cli generate
export OPENROUTER_KEY=[your_openrouter_api_key]
```

## 使い方

### CLI

`src` ディレクトリから実行：

```bash
uv run python main.py [options]
```

### オプション

| フラグ | デフォルト | 説明 |
|--------|-----------|------|
| `--players N` | `3` | プレイヤー数 (3〜10) |
| `--wolves N` | `1` | 狼の数 (1〜[プレイヤー数の1/2]) |
| `--rounds N` | `2` | 議論ラウンド数 |
| `--games N` | `1` | 連続実行するゲーム数 (CLIのみ) |
| `--lang LANG` | English | 議論の言語 (例：`Japanese`、`French`) |
| `--models m1,m2,...` |  (デフォルトクライアント) | カンマ区切りのOpenRouterモデルID。プレイヤーごとに指定するか、全プレイヤーに同一モデルを指定 |
| `--reflection` | オフ | ゲーム後の振り返りフェーズを実行 (各エージェントが自分のプレイを振り返る) |
| `--human` | オフ | 人間プレイヤーとしてゲームに参加 (`--wolf-indices`と同時使用不可) |
| `--html` | オフ | HTMLリプレイ出力を保存 |

### 高度なオプション

主にLLM実験・研究向けのオプションです。

| フラグ | デフォルト | 説明 |
|--------|-----------|------|
| `--hide-thinking` | オフ | 各エージェントの非公開の推論を非表示にする |
| `--no-advice` | オフ | 議論プロンプトからの戦略アドバイスを非表示にする (後述) |
| `--json` | オフ | リプレイJSONを保存 |
| `--wolf-indices 0,2` | ランダム | 狼のプレイヤーインデックス (0始まり)をカンマ区切りで指定 |
| `--word-pair-index N` | ランダム | 単語ペアリストのインデックス (0始まり) |
| `--word-pair W1 W2` | なし | 市民の単語と狼の単語を直接指定 (ランダム選択をスキップ。`--word-pair-index`と同時使用不可) |
| `--generate-word-pair` | オフ | LLMで新しい単語ペアを生成 (`--word-pair`や`--word-pair-index`と同時使用不可) |
| `--seed N` | なし | 発言順序とタイブレークを再現するためのランダムシード |
| `--game-id ID` | なし | JSON出力に含まれる実験識別子 |
| `--output-dir DIR` | `../replay` | リプレイファイルの出力ディレクトリ |
| `--continue JSON_FILE` | なし | 以前に保存したJSONファイルから継続 (`--games`が必要。後述) |
| `--prompt-debug` | オフ | プロンプトのデバッグログを有効にする |

### マルチゲームCLI実行

`--games N`はCLIでのみサポートされています。Web UIはシングルゲームのままです。

- `--games >= 2`の場合、CLIは`N`ゲームを連続実行し、最後にプレイヤーごとの統計を表示します。
- `--games >= 2 --reflection`を使用すると、各プレイヤーの反省と教訓(lessons learned)が次のゲームに引き継がれ、プレイのたびに洗練されます。
- 単語ペアがランダム選択の場合 (`--word-pair`、`--word-pair-index`、`--generate-word-pair`のいずれも未指定)、バッチ内の各ゲームは異なる単語ペアを使用します。定義済みペアをすべて使い切ると、再びすべてのペアが使用可能になります。

#### `--continue` オプション

`--continue`を使うと、以前に保存したJSONファイルを読み込んで追加ゲームを実行することで、完了した実験を延長できます。ゲーム設定 (プレイヤー数、狼数、ラウンド数、モデル、言語など)、反省と教訓(lessons learned)、使用済み単語ペアはすべてJSONから引き継がれます。

```bash
# 最初の5ゲームを実行
uv run python main.py --games5--reflection --json

# 保存したJSONから5ゲーム追加で続行
uv run python main.py --continue ../replay/wordwolf_replay_20250101_120000.json --games 5
```

- `--continue`には`--games N`が必要です
- `--json`は自動的に有効になります (結合結果は常にJSONとして保存されます)
- ゲーム番号、プレイヤー統計、lessons learnedは前回の続きから引き継がれます
- 前のゲームで使用した単語ペアはランダム選択から除外されます
- `--players`、`--wolves`、`--rounds`、`--models`、`--reflection`などの設定は上書き不可で、JSONから引き継がれます
- シングルゲームおよびマルチゲームのJSONファイルのどちらも入力として使用できます

#### `--no-advice` オプション

デフォルトでは、議論プロンプトに **「話し方」** セクションが含まれており、各エージェントに明示的な戦略ガイダンスが与えられます。たとえば、他のプレイヤーのヒントから自分が市民か狼かを推測する方法、疑いをかわす方法、他のプレイヤーを探る質問をするタイミングなどです。

`--no-advice`を使用するとこのセクションが完全に削除されます。エージェントにはゲームの基本ルールのみが伝えられ、戦略は自分で考えなければなりません。これは、事前に書かれたヒューリスティックなしでLLMの純粋な戦略的推論能力を測定するのに役立ちます。

```bash
# 組み込みアドバイスなしで戦略的推論を測定
uv run python main.py --no-advice
```

### 使用例

```bash
# デフォルトの3人ゲーム (クイックスタート)
uv run python main.py

# 10ゲームを連続実行してプレイヤーごとの統計を表示
uv run python main.py --games 10

# LLM エージェントと対戦 (人間プレイヤーとして参加)
uv run python main.py --human --players 5

# 6人、狼2人、3ラウンド
uv run python main.py --players 6 --wolves 2 --rounds 3

# 日本語でプレイしてHTMLリプレイを保存
uv run python main.py --players5--lang Japanese --html

# リフレクション付きマルチゲーム実行と集約 JSON
uv run python main.py --games5--reflection --json --html

# 前回の実行をさらに3ゲーム継続
uv run python main.py --continue ../replay/wordwolf_replay_20250101_120000.json --games 3

# エージェントの推論を非表示にする
uv run python main.py --hide-thinking

# 全プレイヤーに同じモデルを使用
uv run python main.py --models "anthropic/claude-opus-4.6" --players 5

# マルチモデル実験:3種類のモデル、プレイヤー0が狼、単語ペアとシードを固定
uv run python main.py \
  --models "openai/gpt-5.4,anthropic/claude-opus-4.6,google/gemini-3.1-pro-preview" \
  --wolf-indices 0 \
  --word-pair-index5\
  --seed 42 \
  --game-id "block1_game1" \
  --json --output-dir ../results
```

### Web UI

`src` ディレクトリから実行：

```bash
uv run python web_app.py
```

Webブラウザで `http://localhost:5000` を開いてください。Web UIではAIのプレイを観戦したり、人間プレイヤーとして参加したりできます。単語ペアはゲームごとにLLMによって生成されます。

## マルチモデル実験

`--models`で各プレイヤーに異なるLLMモデルを割り当てることができます。`--wolf-indices`、`--word-pair-index`、`--seed`と組み合わせることで、社会的推理におけるモデルの能力を比較する完全に制御された実験が可能です。

`--game-id`と`--seed`フィールドは実験追跡のためにJSON出力に含まれます

## プロジェクト構成

```
src/
├── main.py              # CLIエントリーポイント (argparse、CLIEventHandler、CLIInputProvider)
├── engine.py            # GameEngineクラス、プロトコル (GameEventHandler、InputProvider)、コアゲームロジック
├── models.py            # データクラス (GameConfig、GameRecord など)と定数
├── rendering.py         # HTML/JSONレンダリングとファイル出力
├── word_pairs.py        # 市民/狼の単語として使用する単語ペア
├── templates/
│   └── game_report.html #HTMLリプレイテンプレート
└── baml_src/
    ├── clients.baml     # LLM クライアント定義 (OpenRouter)
    ├── types.baml       # BAML データ型
    └── game.baml        # プロンプト: Discuss、Vote、GuessWord、JudgeGuess、Reflect
```

`src/baml_client/`は自動生成されますので、直接編集しないでください。`.baml`ファイルを変更した後は、以下のコマンドで再生成してください：

```bash
cd src
uv run baml-cli generate
```

## カスタマイズ

| 変更したい内容 | 編集するファイル |
|----------------|-----------------|
| ゲームで使用する単語ペア | `src/word_pairs.py` |
| プレイヤー名 | `src/models.py` の定数 |
| LLMモデル | `src/baml_src/clients.baml` |
| LLMプロンプト | `src/baml_src/game.baml` |

`.baml`ファイルを編集した後は、クライアントを再生成してください：

```bash
cd src
uv run baml-cli generate
```

## クレジット

ワードウルフは**川崎晋氏**によってデザインされました。本実験プログラムは氏の作品にインスパイアされています。
