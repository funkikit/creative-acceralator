# プロトタイプ作成加速器

FastAPI ベースの API でクリエイティブ向けバリエーションを生成し、Next.js UI と連携して評価・集計までを支援する社内 PoC 用プラットフォームです。変数抽出 → 生成 → 画像評価 → サマリーというワークフローをワンストップで提供し、Cloud Run へワンクリックで再デプロイできるよう設計されています。

## 📦 主な構成要素

- **API (app/)**: FastAPI + structlog。バリエーション生成、画像生成、評価、サマリー API を提供。
- **フロントエンド (frontend-next/)**: Next.js 14。生成・評価フローを操作する保護付き UI。
- **補助 UI (frontend/)**: Streamlit ベースの検証 UI（必要に応じて利用）。
- **インフラ (infra/, cloudrun/)**: Dockerfile / Cloud Run デプロイスクリプト / Secret Manager 連携。
- **テスト (tests/)**: pytest によるユニット & スモークテスト。

## 🗂️ ディレクトリ構成

| パス | 内容 |
| --- | --- |
| `app/api` | FastAPI ルーター (`/api/variations`, `/api/images`, `/api/validate`, `/api/summary`) |
| `app/services` | 生成・評価ロジック、外部 API 連携 |
| `app/models` | Pydantic モデル、DB モデル |
| `app/utils` | ロガー、外部クライアント共通処理 |
| `frontend-next` | Next.js アプリ本体（`app/`, `components/`, `lib/` 等） |
| `cloudrun` | デプロイスクリプト、環境変数ファイル、Config テンプレート |
| `infra` | `Dockerfile`（API 用）、`Dockerfile.frontend`（Next.js 用） |
| `docs/cloudrun_deployment.md` | Cloud Run へのデプロイ手順（Secret Manager 同期を含む） |

## ✅ 前提条件

- Python 3.11 (uv パッケージマネージャーを利用)
- Node.js 20（Next.js ビルド用）
- Google Cloud SDK (`gcloud`)
- Docker / Cloud Build を利用できる GCP プロジェクト

必要な CLI インストール例:

```bash
brew install uv node
# gcloud は https://cloud.google.com/sdk からインストール
```

## 🚀 Getting Started

### 1. 依存関係のセットアップ

```bash
uv sync  # pyproject.toml / uv.lock を基に Python 依存をインストール
```

Node パッケージは Next.js ビルド時に自動で `npm ci` されます（`infra/Dockerfile.frontend` の deps ステージ）。ローカル開発で Next.js を直接動かす場合は手動でインストールしてください。

```bash
cd frontend-next
npm ci
```

### 2. 環境変数

- **ローカル**: `app` 直下の `.env` や `infra/.env.example` を参考に必要なキーを設定（OpenAI/Gemini/GCS 等）。
- **Cloud Run**: `cloudrun/app.env`（API 用）、`cloudrun/frontend.env`（Frontend 用）に `KEY=value` 形式で記入。`./cloudrun/deploy.sh` 実行時に Secret Manager へ自動同期されます。

主なキー例

| KEY | 用途 |
| --- | --- |
| `OPENAI_API_KEY` / `GEMINI_API_KEY` | LLM 呼び出し用
| `GCS_BUCKET` / `GCS_PREFIX` | 生成画像の保存先設定
| `CORS_ORIGINS` | フロントエンド URL（複数指定はカンマ区切り）
| `NEXT_PUBLIC_API_BASE_URL` | フロントエンドから叩く API のベース URL（Cloud Run API URL を指定）

### 3. ローカル実行

#### API (FastAPI)

```bash
uv run fastapi run app.main:app --reload
# または uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

#### フロントエンド (Next.js)

```bash
cd frontend-next
npm run dev
```

ログイン保護が掛かっているため、`frontend-next/app/(auth)/login` のフォームに PoC 用パスワード（`frontend.env` の `POC_ACCESS_PASSWORD`）を入力してください。

#### Streamlit UI（任意）

```bash
uv run streamlit run frontend/app.py
```

### 4. テスト / Lint

```bash
uv run pytest -q                     # ユニットテスト
uv run ruff check .                  # Lint
uv run ruff format .                 # フォーマッター（--check で Dry run）
```

## ☁️ Cloud Run へのデプロイ

1. `cloudrun/config.example.sh` を `cloudrun/config.sh` にコピーし、プロジェクト ID や Artifact Registry リポジトリ名、サービス名を設定。
2. `cloudrun/app.env` / `cloudrun/frontend.env` に本番用環境変数を記入。
3. Docker Hub 認証が必要な場合は PAT を Secret Manager に保存し、`DOCKER_HUB_USERNAME_SECRET` / `DOCKER_HUB_PASSWORD_SECRET` を `config.sh` に設定。
4. `FRONTEND_BUILD_ARGS="NEXT_PUBLIC_API_BASE_URL"` を有効化すると、Next.js ビルド時に API URL が静的に埋め込まれます。
5. デプロイ実行:
   ```bash
   ./cloudrun/deploy.sh api        # FastAPI のみ
   ./cloudrun/deploy.sh frontend   # Next.js のみ
   ./cloudrun/deploy.sh all        # 両方同時
   ```
   - Cloud Build が Docker イメージをビルドし Artifact Registry へ push
   - Secret Manager に環境変数を同期し、Cloud Run を更新

詳細な手順・トラブルシューティングは `docs/cloudrun_deployment.md` を参照してください。

## 🔍 トラブルシューティング

- **API 呼び出しがローカルホストに向かう**: `cloudrun/config.sh` の `FRONTEND_BUILD_ARGS` と `cloudrun/frontend.env` の `NEXT_PUBLIC_API_BASE_URL` を確認。再デプロイでバンドルに反映されます。
- **CORS エラー**: `cloudrun/app.env` の `CORS_ORIGINS` に最新のフロント URL が含まれているか確認。
- **Artifact Registry 認証失敗**: `gcloud auth configure-docker asia-northeast1-docker.pkg.dev` を実行後に再ビルド。
- **Secret Manager の値が古い**: `gcloud secrets versions access <name>` で確認し、`gcloud secrets versions add` で更新。

## 🤝 コントリビュート手順

1. Issue / タスクを確認
2. ブランチ作成 (`feature/...`)
3. コード修正 + テスト・lint 実行
4. Conventional Commits 形式でコミット
5. PR に変更概要、再現手順、スクリーンショット（UI 変更時）、テスト結果を記載

---

セットアップやデプロイで不明点があれば `docs/` 配下や `cloudrun/deploy.sh` のログを参照してください。Cloud Run へのワンコマンド再デプロイと Secret Manager 連携により、ジュニアエンジニアでも安全に本番相当環境を更新できます。
