# Cloud Run デプロイメントガイド

このガイドは、FastAPI バックエンド（`app/`）と Next.js フロントエンド（`frontend-next/`）を Google Cloud Run にデプロイするための手順を、ジュニアエンジニアでも再現できるよう順を追って説明します。

## 1. 前提条件

- 請求が有効な Google Cloud プロジェクト（または作成する権限）。
- ローカルに Google Cloud SDK（`gcloud`）をインストール済みで、`gcloud init` による認証が完了していること。
- 必要な IAM 権限：
  - `roles/owner`、または以下の組み合わせ
    - `roles/run.admin`
    - `roles/artifactregistry.admin`
    - `roles/cloudbuild.builds.editor`
    - `roles/secretmanager.admin`
    - `roles/iam.serviceAccountUser`
- 本リポジトリにアクセス可能なローカル環境。
- 初回デプロイをスムーズにするため、Cloud Console で Cloud Run Admin API を事前に有効化しておくと良いです。

## 2. gcloud の初期設定

```bash
# 利用するプロジェクトとリージョンを設定
PROJECT_ID="creation-acceralation-proto"
REGION="asia-northeast1"

gcloud config set project "$PROJECT_ID"
gcloud config set run/region "$REGION"
```

## 3. 必要な Google Cloud API を有効化

デプロイスクリプト内でも有効化処理を行いますが、事前に以下を実行して確認できます。

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com
```

## 4. サービスアカウントの作成（推奨）

Cloud Run 向けに専用サービスアカウントを用意することで、最小権限ポリシーを適用しやすくなります。

```bash
# API 用サービスアカウント
API_SA="pca-api@${PROJECT_ID}.iam.gserviceaccount.com"
gcloud iam service-accounts create pca-api --display-name "PCA API"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${API_SA}" \
  --role="roles/storage.objectAdmin"

# フロントエンド用サービスアカウント
FRONTEND_SA="pca-frontend@${PROJECT_ID}.iam.gserviceaccount.com"
gcloud iam service-accounts create pca-frontend --display-name "PCA Frontend"
```

アプリケーションが追加の GCP サービスへアクセスする場合は、必要なロールを適宜付与してください。

## 5. Artifact Registry の準備

コンテナイメージを格納する Docker リポジトリを決めます。デプロイスクリプトが初回デプロイ時に自動作成しますが、以下で明示的に作成しておくこともできます。

```bash
REPO="pca-services"
gcloud artifacts repositories create "$REPO" \
  --repository-format=docker \
  --location="$REGION" \
  --project="$PROJECT_ID"
```

### 5.1 Docker Hub 認証情報の登録（任意 / Docker Hub を利用する場合）

Cloud Build はデフォルトで Docker Hub に認証なしでアクセスします。レート制限やプライベートイメージに対応するため、Docker Hub のアクセストークン（Personal Access Token）を Secret Manager に保存し、ビルド前に `docker login` を実行できるようにします。

1. Docker Hub の [Account Settings → Security](https://hub.docker.com/settings/security) からアクセストークンを発行し、ユーザー名とトークンを控えます。
2. Secret Manager にユーザー名・トークンをそれぞれ保存します。
   ```bash
   gcloud secrets create docker-hub-username \
     --project "$PROJECT_ID" \
     --replication-policy automatic \
     --data-file=<(printf '%s' 'your-docker-username')

   gcloud secrets create docker-hub-password \
     --project "$PROJECT_ID" \
     --replication-policy automatic \
     --data-file=<(printf '%s' 'your-access-token')
   ```
   すでにシークレットが存在する場合は、`secrets create` の代わりに `gcloud secrets versions add` を使用して値を更新します。
3. `cloudrun/config.sh` に以下を追記し、使用するシークレット名を指定します。
   ```bash
   export DOCKER_HUB_USERNAME_SECRET="docker-hub-username"
   export DOCKER_HUB_PASSWORD_SECRET="docker-hub-password"
   ```

設定を反映すると、デプロイスクリプトが Cloud Build のビルドステップで自動的に `docker login` を実行し、Docker Hub からベースイメージを取得できるようになります。

## 6. Cloud Run 用環境変数ファイルの準備

Secret Manager に同期する値を `cloudrun` ディレクトリ内の下記ファイルに記載します。機密値を含む場合は Git にコミットしないでください。

- バックエンド: `cloudrun/app.env`
- フロントエンド: `cloudrun/frontend.env`

形式は `KEY=value` を 1 行ずつ記載します。`#` で始まる行は無視されます。`${GCS_BUCKET}` のようなプレースホルダーは、Secret Manager に保存する際に解決済みの値へ置き換えてください。

## 7. デプロイ設定ファイルの作成

1. サンプル設定をコピーし、環境ごとのファイルを作成します。
   ```bash
   cp cloudrun/config.example.sh cloudrun/config.sh
   ```
2. `cloudrun/config.sh` を編集し、最低限以下を設定します。
   - `GCP_PROJECT_ID`, `GCP_REGION`
   - `ARTIFACT_REGISTRY_REPO`
   - `API_IMAGE_URL`, `FRONTEND_IMAGE_URL`
   - `API_SERVICE_NAME`, `FRONTEND_SERVICE_NAME`
   - `API_SECRET_PREFIX`, `FRONTEND_SECRET_PREFIX`
   - 必要に応じて `API_SERVICE_ACCOUNT`, `FRONTEND_SERVICE_ACCOUNT`, VPC 接続、リソースサイズなどを上書きします。
3. ステップ 4 でサービスアカウントを作成した場合は、このファイルに記載して Cloud Run 実行時のアイデンティティとして指定してください。

シークレット名は `<prefix>-<env_key_in_lowercase>` 形式（例: `pca-api-openai-api-key`）で作成されます。プレフィックスを安易に変更すると使われないシークレットが残ってしまうため注意してください。

## 8. Secret Manager 同期の挙動

デプロイスクリプトを実行すると、コンテナをビルドする前に対象サービスの環境変数ファイル内のキーが順番に Secret Manager へ同期されます。既存のシークレットがあれば新しいバージョンを追加し、なければ作成します。

値を更新したい場合は、ローカルの環境変数ファイルを書き換えた後で再度該当サービスのデプロイコマンドを実行してください。シークレットの新バージョン追加と Cloud Run の再デプロイが一度に行われます。

## 9. バックエンド（FastAPI）のデプロイ

```bash
./cloudrun/deploy.sh api
```

実行される処理は以下の通りです。

1. 必要な Google Cloud API を有効化（冪等）。
2. Artifact Registry リポジトリを作成または更新。
3. Artifact Registry への Docker 認証を設定。
4. `cloudrun/app.env` の各キーを `API_SECRET_PREFIX` に基づく Secret Manager シークレットへ同期。
5. Cloud Build によるコンテナイメージのビルドとプッシュ。
6. Cloud Run サービスをデプロイし、すべての環境変数を Secret Manager の最新バージョンにマッピング。

デプロイ完了後、サービス URL を確認します。

```bash
gcloud run services describe "$API_SERVICE_NAME" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --format='value(status.url)'
```

## 10. フロントエンド（Next.js）のデプロイ

```bash
./cloudrun/deploy.sh frontend
```

バックエンドと同様に、`cloudrun/frontend.env` をシークレット化し、フロントエンド用 Dockerfile を使ってデプロイします。

サービス URL の取得例：

```bash
gcloud run services describe "$FRONTEND_SERVICE_NAME" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --format='value(status.url)'
```

## 11. コード更新後のワンコマンド再デプロイ

- バックエンドのみ: `./cloudrun/deploy.sh api`
- フロントエンドのみ: `./cloudrun/deploy.sh frontend`
- 両方まとめて: `./cloudrun/deploy.sh all`

イメージタグはデフォルトで現在の git コミット SHA（`git rev-parse --short HEAD`）から取得します。CI ビルド番号など任意のタグを使いたい場合は、`cloudrun/config.sh` で `IMAGE_TAG` を指定してください。

## 12. 環境変数変更時のフロー

1. `cloudrun/app.env` または `cloudrun/frontend.env` を編集。
2. 対応するサービスのデプロイスクリプトを実行。
3. Cloud Run コンソールで最新リビジョンを確認し、必要に応じてロールバック。

## 13. トラブルシューティング

- **Secret Manager シークレット作成で権限エラー**: `roles/secretmanager.admin` が付与されているか確認。
- **Artifact Registry 認証エラー**: `gcloud auth configure-docker REGION-docker.pkg.dev` を手動で実行し再度デプロイ。
- **実行時に環境変数が見つからない**: env ファイルにキーが存在するか、シークレット名が正しいか、デプロイがエラーなく完了したか確認。
- **古いイメージが使われる**: Cloud Run のリビジョンで期待するイメージタグが使われているか確認し、不要なリビジョンを削除。

以上の手順を守ることで、設定のドリフトを防ぎながら Secret Manager を通じて機密情報を管理し、バックエンド・フロントエンド双方をワンコマンドで再デプロイできる運用体制を構築できます。
