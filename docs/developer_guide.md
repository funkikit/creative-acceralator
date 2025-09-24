# 開発者ガイド（ジュニアエンジニア向け）

本ドキュメントは、本リポジトリの構成・開発フロー・運用方法を、FastAPI/Streamlit 初学者でも理解できるように丁寧に解説します。将来的に Next.js などのリッチなフロントエンドへ移行しやすい設計も意識しています。

---

## 1. プロジェクト全体像

- バックエンド: FastAPI（生成・評価・集計 API）
  - サービス層で外部クライアント（LLM, 画像生成）を抽象化
  - Pydantic で入出力スキーマを厳格化
  - 簡易メモリ（`app/api/state.py`）で E2E フローをつなぐ
- フロントエンド: Streamlit の最小 UI（将来は Next.js へ移行可能）
- インフラ: Docker/Docker Compose、`.env` によりキー・設定を注入
- テスト: pytest でユニット/E2E スモーク
- ツール: `uv`（依存管理/実行）、`ruff`（Lint/Format）

ディレクトリ（抜粋）:

```
app/
  api/             # ルーティング（APIRouter）とアプリ状態
  models/          # Pydantic スキーマ
  services/        # ビジネスロジック（生成/評価/集計）
  utils/           # 外部クライアントやユーティリティ
  main.py          # FastAPI エントリポイント
frontend/
  app.py           # Streamlit UI
  api_client.py    # バックエンド呼び出しを集約
infra/
  Dockerfile, docker-compose.yml, .env.example
tests/
docs/
```

---

## 2. セットアップと起動

前提:
- Python 3.11+
- uv（`pip install uv` または公式手順）

手順:
1) 依存インストール

```
uv sync
```

2) 環境変数ファイルの作成

```
cp infra/.env.example .env
# 必要に応じて API キーなどを設定
```

3) バックエンド起動（開発）

```
uv run fastapi run app.main:app --reload
```

4) フロントエンド起動（別ターミナル）

```
uv run streamlit run frontend/app.py
```

5) テスト / Lint

```
uv run pytest -q
uv run ruff check .
uv run ruff format .
```

Docker:

```
docker build -f infra/Dockerfile -t pca-api .
docker compose -f infra/docker-compose.yml up
```

---

## 3. FastAPI の基本（本プロジェクトでの使い方）

- ルーティングは `app/api/routes_*.py` に分割し、`APIRouter` を使ってエンドポイント群を整理します。
- `app/main.py` でルーターをまとめて `app.include_router(...)` します。
- Pydantic の `BaseModel` を使って Request/Response を型定義します（`app/models/schemas.py`）。
- DI（依存性注入）には FastAPI の `Depends` を使用します。サービス層（例: `VariationService`）を引数として受け取る形にしてテスト容易性を高めます。
- 静的ファイルは `/static` で配信（`app/main.py` の `StaticFiles`）。画像生成の成果物を UI から表示できます。

リクエスト/レスポンスはすべて JSON。OpenAPI ドキュメントは `http://localhost:8000/docs`（Swagger UI）/ `.../redoc` から参照できます。

---

## 4. API レイヤの構成

主要エンドポイント:
- POST `/api/variations`: 基本プロンプトからクリエイティブ案（バリエーション）を生成
- POST `/api/images`: バリエーション ID から画像を生成（/static に保存、URL を返却）
- POST `/api/validate`: 画像に対しペルソナ群でスコアリング
- GET `/api/summary`: 評価結果を集計（全体/グループ/ランキング）

内部構造（簡易メモリ）:
- `state.variations`: 生成済みバリエーションの辞書
- `state.images`: 生成済み画像メタの辞書
- `state.evaluations`: 評価結果の配列

サービス層:
- `services/variation.py`: 変数抽出→プロンプト生成（LLM 経由）
- `services/image_gen.py`: 画像生成（`GeminiImageClient`）→ `/static` 保存
- `services/validation.py`: ペルソナをサンプリング（CSV）→ LLM でスコアリング
- `services/aggregation.py`: pandas で統計集計

ユーティリティ:
- `utils/llm_client.py`: LLM 呼び出しの薄い抽象。実装は NotImplemented（テストでモック/モンキーパッチ）
- `utils/image_client.py`: 画像生成クライアント（HTTP 経由）
- `utils/storage.py`: 絶対パス→公開 URL（/static）への変換
- `utils/sampler.py`: CSV からの擬似ペルソナ抽出

---

## 5. データフロー（E2E）

1) Variations: 基本プロンプト→ `VariationService` が LLM を用いて `VariationOut[]` を生成。`state.variations` にキャッシュ。
2) Images: 選択した Variation ID 群→ `ImageService` が画像を生成し `/static` へ保存、`state.images` にキャッシュ。
3) Validate: 画像 ID 群→ `ValidationService` が複数ペルソナでスコアリングし `EvaluationOut[]` を返す。`state.evaluations` にキャッシュ。
4) Summary: `aggregation.summarize` が全体平均・グループ集計・画像ランキングを返す。

Streamlit UI はこの順でエンドポイントを順に呼び出します（`frontend/api_client.py` 経由）。

---

## 6. スキーマ（Pydantic）

場所: `app/models/schemas.py`

- VariationsRequest/Response, ImagesRequest/Response, ValidateRequest/Response を定義
- `EvaluationOut` は `scores`（複数指標 + overall）と `comment`、`flags[]` を持つ
- バリデーションは Pydantic の Field 制約（例: `k: int = Field(10, ge=1, le=32)`）で記述

スキーマを変更した場合、テストと UI（`ApiClient`／ビュー）も更新してください。

---

## 7. 依存性注入（Depends）とテスト容易性

例: `routes_variation.svc()` は `VariationService` を組み立て、`Depends(svc)` でエンドポイントに注入します。

利点:
- サービス層の入れ替えが容易（本番/モック）
- 単体テスト時に LLM/画像生成の外部依存を差し替え可能

テストでは `monkeypatch` を使い、`LLMClient.complete` や `GeminiImageClient.generate_png` をスタブ化します。

---

## 8. エラーハンドリングとロギング

- サービス層で発生した例外は FastAPI では 500 になります。ユーザー要因（入力不備）には `HTTPException(status_code=400, detail=...)` を明示的に返す設計を推奨。
- 本プロジェクトは `structlog` の導入を推奨（AGENTS.md 記載）。今後、`uvicorn` の access log と整合する JSON 構造で `trace_id` 等を付与すると運用で可視性が高まります。
- 代表的な場所で try/except を置き、`logger.exception(...)` を行うとよいです。

---

## 9. 環境変数と秘密情報

- `.env` をプロジェクトルートに置く（`infra/.env.example` をコピー）。
- 代表的な変数:
  - `GEMINI_API_KEY`: 画像生成 API 用キー（未設定だと画像生成は失敗）
  - `GEMINI_IMAGE_MODEL`: 画像モデル名（デフォルト `gemini-nanobanana`）
  - `STATIC_DIR`: 画像出力ディレクトリ（デフォルト `app/static`）
- `.env` はコミット禁止。CI/CD ではシークレットとして管理。

---

## 10. フロントエンド（Streamlit → Next.js へ移行しやすく）

- Streamlit 側では HTTP 呼び出しを `frontend/api_client.py` に集約（UI と輸送層の分離）。
- 今後 Next.js 化する際は、`api_client.py` を元に OpenAPI から TypeScript クライアント生成（or 手書き）に置き換えやすい構成。
- UI はタブで Variations → Images → Validate → Summary のステップを分離し、状態は `st.session_state` に保持。

---

## 11. 新しいエンドポイント追加手順（例）

例: `/api/examples` に新機能を追加する場合

1) スキーマ作成（`app/models/schemas.py`）

```python
class ExampleRequest(BaseModel):
    text: str

class ExampleResponse(BaseModel):
    result: str
```

2) サービス作成（`app/services/example.py`）

```python
class ExampleService:
    async def run(self, text: str) -> str:
        return text.upper()
```

3) ルート作成（`app/api/routes_example.py`）

```python
from fastapi import APIRouter, Depends
from app.models.schemas import ExampleRequest, ExampleResponse
from app.services.example import ExampleService

router = APIRouter(prefix="/api/examples", tags=["examples"])

def svc():
    return ExampleService()

@router.post("", response_model=ExampleResponse)
async def create(req: ExampleRequest, s: ExampleService = Depends(svc)):
    return ExampleResponse(result=await s.run(req.text))
```

4) ルータを `app/main.py` に登録

```python
from app.api import routes_example
app.include_router(routes_example.router)
```

5) テスト追加（`tests/test_example.py`）→ 最低限のリクエスト/レスポンス検証

6) UI との接続（`frontend/api_client.py` にメソッド追加→ `frontend/app.py` でボタン/表示）

---

## 12. 非同期とパフォーマンス

- FastAPI は非同期対応。外部 I/O（HTTP 呼び出しなど）は `httpx.AsyncClient` を使い await で並列性を確保。
- 応答のスループットを上げるには、サービス層でタスクを集めて `asyncio.gather` などの活用も検討。
- 重い計算はワーカー（RQ/Celery）やバッチに逃がす設計も有効。

---

## 13. セキュリティ

- 認証・認可は PoC 段階では未実装。将来的には：
  - API Key / OAuth2（JWT）
  - CORS 制限（`fastapi.middleware.cors.CORSMiddleware`）
- 入力バリデーション: Pydantic でスキーマを厳密化し、サービス層では受け取ったデータの二次検証を行う。
- 出力（HTML 表示）は UI 側でエスケープ（Streamlit/Next.js は基本安全だが、埋め込み時は注意）。

---

## 14. 運用（Docker / Compose）

- `infra/Dockerfile` によりアプリをコンテナ化。
- `infra/docker-compose.yml` で API + 将来の DB/ワーカーなどを統合起動可能。
- `.env` を Compose から読み込み、キーを注入。
- `app/static` の永続化が必要ならボリュームマウントを検討。

---

## 15. テスト戦略

- 目標: コア（`services/`, `api/`）でカバレッジ 80% 以上。
- パターン:
  - ユニット: サービス層の純粋ロジック検証
  - 結合/E2E スモーク: `/variations → /images → /validate → /summary` の一連
- 外部依存（LLM/画像生成）はモック/スタブ必須。

例: `LLMClient.complete` をモンキーパッチ

```python
def fake_complete(system: str, user: str) -> str:
    return '{"prompt":"...","scores":{"overall":0.9},"comment":"ok"}'

monkeypatch.setattr("app.utils.llm_client.LLMClient.complete", lambda *a, **k: fake_complete(*a[1:], **k))
```

---

## 16. 典型的なトラブルと対処

- 画像生成が失敗する: `GEMINI_API_KEY` 未設定。`.env` を確認。
- 422 Unprocessable Entity: リクエスト JSON がスキーマに合っていない。キー名/型を見直す。
- CORS エラー（将来ブラウザ SPA で）: CORS Middleware の設定を追加。
- `/static/...` が 404: 画像生成自体が失敗 or `STATIC_DIR` の不一致。`app/main.py` のマウント先と一致させる。

---

## 17. 次の一歩（拡張案）

- OpenAPI からの TypeScript クライアント生成（Next.js へ移行準備）
- 構造化ロギング（`structlog`）と分散トレーシング（`trace_id`）
- 永続 DB（SQLite→Postgres）化と履歴管理
- キュー（RQ/Celery）による非同期ジョブ化

---

## 18. 参考リンク

- FastAPI: https://fastapi.tiangolo.com/
- Pydantic v2: https://docs.pydantic.dev/
- httpx: https://www.python-httpx.org/
- Streamlit: https://docs.streamlit.io/
- uv: https://github.com/astral-sh/uv
- Ruff: https://docs.astral.sh/ruff/

