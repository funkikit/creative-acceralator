#!/usr/bin/env bash
# Copy this to cloudrun/config.sh and adjust per environment.
# Only include non-sensitive configuration here.

# GCP project and region
export GCP_PROJECT_ID="your-gcp-project-id"
export GCP_REGION="asia-northeast1"

# Artifact Registry repository settings
export ARTIFACT_REGISTRY_REPO="pca-services"
export ARTIFACT_REGISTRY_LOCATION="$GCP_REGION"

# Cloud Run service names
export API_SERVICE_NAME="pca-api"
export FRONTEND_SERVICE_NAME="pca-frontend"

# Container image URLs (repository path without tag)
# Example: asia-northeast1-docker.pkg.dev/<project>/<repository>/<image-name>
export API_IMAGE_URL="asia-northeast1-docker.pkg.dev/${GCP_PROJECT_ID}/${ARTIFACT_REGISTRY_REPO}/api"
export FRONTEND_IMAGE_URL="asia-northeast1-docker.pkg.dev/${GCP_PROJECT_ID}/${ARTIFACT_REGISTRY_REPO}/frontend"

# Source env files (stored locally and synced to Secret Manager)
export API_ENV_FILE="cloudrun/app.env"
export FRONTEND_ENV_FILE="cloudrun/frontend.env"

# Prefixes used when creating secrets for each environment variable
export API_SECRET_PREFIX="pca-api"
export FRONTEND_SECRET_PREFIX="pca-frontend"

# Dockerfiles for builds
export API_DOCKERFILE="infra/Dockerfile"
export FRONTEND_DOCKERFILE="infra/Dockerfile.frontend"

# Optional static (non-secret) environment variables, comma separated
# Example: API_STATIC_ENV_VARS="LOG_LEVEL=info,ANALYTICS_ENABLED=false"
export API_STATIC_ENV_VARS=""
export FRONTEND_STATIC_ENV_VARS=""

# Optional Docker Hub credentials (store username/password in Secret Manager)
# export DOCKER_HUB_USERNAME_SECRET="docker-hub-username"
# export DOCKER_HUB_PASSWORD_SECRET="docker-hub-password"

# Default Cloud Run runtime settings (can be overridden per service below)
export CLOUD_RUN_CPU="1"
export CLOUD_RUN_MEMORY="2Gi"
export CLOUD_RUN_MIN_INSTANCES="0"
export CLOUD_RUN_MAX_INSTANCES="3"
export CLOUD_RUN_CONCURRENCY="80"
export CLOUD_RUN_TIMEOUT="900"
export CLOUD_RUN_INGRESS="all"
export CLOUD_RUN_ALLOW_UNAUTHENTICATED="true"

# Ports exposed by each service (Cloud Run requires explicit port flag)
export API_PORT="8000"
export FRONTEND_PORT="3000"

# Optional overrides per service (uncomment as needed)
# export API_CPU="2"
# export API_MEMORY="4Gi"
# export API_SERVICE_ACCOUNT="pca-api@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
# export API_VPC_CONNECTOR="projects/${GCP_PROJECT_ID}/locations/${GCP_REGION}/connectors/your-connector"
# export API_VPC_EGRESS="all-traffic"
# export API_MAX_INSTANCES="5"
# export API_MIN_INSTANCES="1"
# export API_ALLOW_UNAUTHENTICATED="false"
# export FRONTEND_SERVICE_ACCOUNT="pca-frontend@${GCP_PROJECT_ID}.iam.gserviceaccount.com"

# Image tag; defaults to current git commit if unset
# export IMAGE_TAG="manual-tag"
