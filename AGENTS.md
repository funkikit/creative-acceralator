# Repository Guidelines

## プロジェクト構成

- `app/`: FastAPI。`api/` ルート、`services/` 生成/評価/集計、`models/` Pydantic/DB、`prompts/`、`utils/`、`static/`、`data/`。
- `frontend/`: Streamlit 検証 UI（`frontend/app.py`）。
- `infra/`: `Dockerfile`、`docker-compose.yml`、`.env.example`。
- `tests/`: 単体・E2E テスト（`test_*.py`）。
- `docs/`: アーキテクチャとディレクトリ説明。

## ビルド・テスト・開発

- 依存インストール: `uv sync`
- API 起動(開発): `uv run fastapi run app.main:app --reload`
- UI 起動: `uv run streamlit run frontend/app.py`
- テスト: `uv run pytest -q`
- Lint/Format: `uv run ruff check .` / `uv run ruff format .`
- Docker: `docker build -f infra/Dockerfile -t pca-api .` → `docker compose -f infra/docker-compose.yml up`

## コーディング規約・命名

- Python は 4 スペース、公開関数は型ヒント必須。
- ファイル/関数/変数は `snake_case`、クラスは `PascalCase`。
- ログは `structlog` を推奨、可能なら `trace_id` を付与。
- Black 互換整形、Ruff で lint と import 整理（`pyproject.toml` に設定）。

## テスト方針

- フレームワーク: `pytest`。`tests/` に実装し、対象モジュールをミラー。
- 目標: コア（`services/`, `api/`）でカバレッジ >= 80%。
- E2E スモーク: `/variations → /images → /validate → /summary`。
- 実行: `uv run pytest --maxfail=1 --disable-warnings -q`

## コミット・PR

- コミットは簡潔な命令形。Conventional Commits（`feat:`, `fix:`, `chore:`）歓迎。
- PR: 説明、関連 Issue、再現手順/スクショ（UI）、テスト/ lint 通過とドキュメント更新を記載。
- 機微情報や大きな生成物はコミットしない（`.env` は除外、生成物は `app/static` まで）。

## セキュリティ/設定

- `.env` は `infra/.env.example` から作成し、LLM/画像 API 鍵を設定。コミット禁止。
- 設定は環境変数優先。プロバイダクライアントは `utils/`、プロンプトは `prompts/` に配置。
- データ/出力は `app/data` と `app/static` に保存し、外部公開しない。
