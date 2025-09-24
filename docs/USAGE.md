# 利用ガイド（セットアップと基本的な使い方）

本ガイドでは、環境変数の設定、ローカル開発・動作確認、API の基本的な呼び方、Docker での実行方法をまとめます。仕様は docs/SPEC.md を参照し、必要に応じて読み返してください。

## 前提
- Python 3.11 以上
- uv（依存管理）
  - インストール例: `pip install uv`（または公式ドキュメントに従う）
- Docker（任意、デプロイ/検証用途）

## 1. 環境変数を設定
1) 雛形をコピー
```
cp infra/.env.example infra/.env
```

2) `infra/.env` を開き、API キーなどを自分の値に設定

主要な環境変数（例）
- `APP_ENV=local`、`APP_PORT=8000`
- OpenAI: `OPENAI_API_KEY`, `OPENAI_TEXT_MODEL=gpt-4o-mini`
- Gemini: `GEMINI_API_KEY`, `GEMINI_TEXT_MODEL=gemini-2.0-flash`, `GEMINI_IMAGE_MODEL=gemini-nanobanana`
- DB: `DB_URL=sqlite:///./app.db`
- 静的ファイル出力: `STATIC_DIR=app/static`（相対パスでローカル保存）

注意:
- 機微情報（API キー）は必ず `.env` にのみ記載し、コミットしないでください。

## 2. 依存インストール
```
uv sync
```

## 3. API 起動（開発）
```
uv run fastapi run app.main:app --reload
```
- デフォルト: `http://127.0.0.1:8000`
- 静的ファイル: `http://127.0.0.1:8000/static/...`

## 4. フロントエンド（Next.js UI）
Next.js ベースの UI は `frontend-next/` にあります。初回は依存をインストールし、環境変数を設定してから起動します。

```
cd frontend-next
npm install                       # もしくは uv run -- npm install
cp .env.example .env.local        # NEXT_PUBLIC_API_BASE_URL, POC_ACCESS_PASSWORD を設定
npm run dev                       # もしくは uv run -- npm run dev
```

- ローカル API を利用する場合、`NEXT_PUBLIC_API_BASE_URL` は `http://127.0.0.1:8000` を指定します。
- `POC_ACCESS_PASSWORD` はバックエンドの `POC_ACCESS_PASSWORD` と揃える必要があります。
- 開発サーバーは `http://127.0.0.1:4000` で待ち受けます。

### 参考: Streamlit UI（旧検証用）
簡易検証用の Streamlit アプリも残しています。

```
uv run streamlit run frontend/app.py
```

## 5. API クイックスタート
以下の例は `curl` を用いた叩き方です。必要に応じて `jq` で結果を整形してください。

1) バリエーション生成（/api/variations）
```
curl -s -X POST http://127.0.0.1:8000/api/variations \
  -H 'Content-Type: application/json' \
  -d '{"base_prompt":"魅力的な日本企業の怪獣のキャラクターデザイン","k":3,"llm":"gemini"}'
```
レスポンスから `variations[].id` を控えます。

2) 画像生成（/api/images）
```
curl -s -X POST http://127.0.0.1:8000/api/images \
  -H 'Content-Type: application/json' \
  -d '{"variation_ids":["v_xxxx","v_yyyy"]}'
```
Gemini 画像 API を呼び出します。`GEMINI_API_KEY` が未設定だと失敗します。返却の `images[].url` は `/static/...` 配下の公開パスです。

3) 検証（/api/validate）
```
curl -s -X POST http://127.0.0.1:8000/api/validate \
  -H 'Content-Type: application/json' \
  -d '{"image_ids":["img_001","img_002"],"n_personas":50,"llm":"openai"}'
```
指定数の仮想ペルソナでスコアリングを実施し、`evaluations` を返します。

4) 集計（/api/summary）
```
curl -s 'http://127.0.0.1:8000/api/summary?group_by=gender,age_band'
```
全体平均、グループ別平均、画像別ランキングを返します。グループキーがデータに含まれない場合は自動的にスキップします。

## 6. テスト / Lint / Format
- テスト実行: `uv run pytest -q`
  - 変動の大きい外部 API はテストでモックしています。
- Lint: `uv run ruff check .`
- Format: `uv run ruff format .`

## 7. Docker で試す
ビルド:
```
docker build -f infra/Dockerfile -t pca-api .
```
起動例（ポートとボリュームは任意調整）:
```
docker run --rm -p 8000:8000 \
  -e STATIC_DIR=/app/app/static \
  --env-file infra/.env \
  pca-api
```
Compose を使う場合:
```
docker compose -f infra/docker-compose.yml up
```

- Next.js フロント: <http://localhost:3000>
- API: <http://localhost:8000>

## 8. トラブルシューティング
- 画像生成で失敗する（Gemini）
  - `GEMINI_API_KEY` が未設定、またはモデル名が無効の可能性。`GEMINI_IMAGE_MODEL` を確認。ローカル検証のみなら、tests ではモックを使用しています。
- `/static` に書き込めない
  - `STATIC_DIR` のパスと権限を確認。ローカルは `app/static` 推奨。
- 集計で KeyError
  - 本実装は存在しないグループキーを自動スキップします（エラーにならない設計）。

## 9. 参考
- 仕様: docs/SPEC.md
- ディレクトリ: docs/dir.md / docs/architecture.md
