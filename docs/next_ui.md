# Next.js UI ガイド

## プロジェクト構成

```
frontend-next/
  app/
    (auth)/login/page.tsx        # パスワード入力画面
    (protected)/layout.tsx       # サイドバー付きレイアウト
    (protected)/creative/page.tsx# クリエイティブ生成画面
    (protected)/evaluation/page.tsx # エージェント評価画面
    api/auth/login/route.ts      # パスワード検証 API
    api/auth/logout/route.ts     # セッション破棄 API
    layout.tsx                   # ルートレイアウト
    page.tsx                     # /creative にリダイレクト
  components/Sidebar.tsx         # サイドバー
  lib/api.ts                     # バックエンド API クライアント
  styles/globals.css             # Tailwind 設定
  package.json / tsconfig.json / tailwind.config.ts など
```

## セットアップ

1. ルートで依存関係をインストールします。Node.js がローカルにあれば `npm` を直接使えますし、Python 開発フローと合わせたい場合は `uv` 経由でも実行できます。

   ```bash
   cd frontend-next
   npm install            # もしくは uv run -- npm install
   ```

2. `.env.example` を `.env.local` にコピーし、必要に応じて編集します。

   ```bash
   cp .env.example .env.local
   # NEXT_PUBLIC_API_BASE_URL と POC_ACCESS_PASSWORD を設定
   ```

3. 開発サーバーを起動します。

   ```bash
   npm run dev            # もしくは uv run -- npm run dev
   ```

   `http://localhost:4000` にアクセスするとパスワード画面が表示されます。

### Docker Compose での起動

FastAPI と Next.js をまとめて立ち上げる場合は `infra/docker-compose.yml` を使用します。

```bash
cd infra
docker compose up --build
```

- API: <http://localhost:8000>
- Next.js フロント: <http://localhost:3000>

`.env` に `POC_ACCESS_PASSWORD` と各種 API Key を定義しておくと、コンテナにも引き継がれます。別環境からアクセスする際は `CORS_ORIGINS` や `NEXT_PUBLIC_API_BASE_URL` を `.env` で上書きしてください。

## UI の流れ

### パスワードゲート

- `/login` でパスワードを入力し、`POC_ACCESS_PASSWORD` と一致した場合だけ Cookie `poc-auth` を付与。
- `middleware.ts` が Cookie を検証し、未認証ユーザーを `/login` にリダイレクトします。

### クリエイティブ画面

- 「実現したいこと」「守ってほしいこと」を入力。
- 「変数を自動抽出」で `/api/variations/variables` が呼ばれ、候補値がテーブルに反映。
- 追加・削除ボタンで変数やカスタムバリエーションを編集。
- 「バリエーションを生成」で `/api/variations` を実行。カード形式で表示され、右上チェックで画像生成対象を選択。
- 「選択したバリエーションから画像生成」で `/api/images` を呼び出し、結果をグリッド表示。
- 画像生成時に任意で 1 枚の参照画像をアップロードでき、Gemini の image-to-image 変換として送信されます。
- 生成済みバリエーション・画像は `localStorage` に保管され、評価画面から再利用可能です。

### エージェント評価画面

- `localStorage` に保存された画像をカード一覧で表示。チェックで対象を選択。
- ペルソナ表（自由編集）と LLM / 評価人数を設定。
- 「エージェント評価を実行」で `/api/validate` を呼び出し、コメントとスコアを表示。
- コメント横に ⚠︎ バッジが付いた場合はフォールバックで生成された結果です。
- 「サマリービューを更新」で `/api/summary` を取得し、平均値・ランキング・属性別を表示します。

## パスワード保護の実装

- サーバーサイドの環境変数 `POC_ACCESS_PASSWORD` と照合。
- 認証成功時に HTTP-only Cookie をセットし、`middleware` で保護。
- パスワードは GCP Secret Manager 等に格納し、デプロイ環境で `POC_ACCESS_PASSWORD` として注入してください。

## Tailwind / デザイン

- Tailwind CSS を利用し、グラデーションボタンや半透明カードを実現。
- 基本配色はダークモード + プライマリのブルーグラデーション。
- 日本語フォントとして `Noto Sans JP` を全体に適用しています。

## 併存運用

- 既存の Streamlit UI (`frontend/app.py`) は変更していないため、検証用途で引き続き使用できます。
- Next.js UI は `npm run dev` で並行起動し、バックエンド（FastAPI）は従来どおり `uv run fastapi run app.main:app --reload` で利用します。
