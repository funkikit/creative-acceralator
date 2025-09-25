#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/config.sh"

if [[ ! -f "${CONFIG_FILE}" ]]; then
  echo "[deploy] Missing ${CONFIG_FILE}. Copy config.example.sh and customise before deploying." >&2
  exit 1
fi

# shellcheck disable=SC1090
source "${CONFIG_FILE}"

require_config() {
  local var_name="$1"
  if [[ -z "${!var_name-}" ]]; then
    echo "[deploy] Missing required configuration: ${var_name}" >&2
    exit 1
  fi
}

if ! command -v gcloud >/dev/null 2>&1; then
  echo "[deploy] gcloud CLI is required. Install the Google Cloud SDK first." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "[deploy] python3 is required for path calculations." >&2
  exit 1
fi

IMAGE_TAG="${IMAGE_TAG:-}"
if [[ -z "${IMAGE_TAG}" ]]; then
  if git -C "${PROJECT_ROOT}" rev-parse HEAD >/dev/null 2>&1; then
    IMAGE_TAG="$(git -C "${PROJECT_ROOT}" rev-parse --short HEAD)"
  else
    IMAGE_TAG="$(date +%Y%m%d%H%M%S)"
  fi
fi

usage() {
  cat <<USAGE
Usage: $(basename "$0") [api|frontend|all]

Builds container images, syncs environment secrets, and deploys the requested service(s) to Cloud Run.
USAGE
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

SERVICE_ARG="$1"
case "${SERVICE_ARG}" in
  api) SERVICES=("api") ;;
  frontend) SERVICES=("frontend") ;;
  all) SERVICES=("api" "frontend") ;;
  *)
    echo "[deploy] Unknown target '${SERVICE_ARG}'." >&2
    usage
    exit 1
    ;;
esac

ensure_env_file() {
  local path="$1"
  if [[ ! -f "${path}" ]]; then
    echo "[deploy] Environment file not found: ${path}" >&2
    exit 1
  fi
}

resolve_path() {
  local input="$1"
  if [[ "${input}" = /* ]]; then
    echo "${input}"
  else
    echo "${PROJECT_ROOT}/${input}"
  fi
}

relative_to_project_root() {
  local target="$1"
  python3 - "${PROJECT_ROOT}" "${target}" <<'PY'
import os
import sys

base = os.path.realpath(sys.argv[1])
target = os.path.realpath(sys.argv[2])
print(os.path.relpath(target, base))
PY
}

trim() {
  local var="$1"
  # shellcheck disable=SC2001
  echo "${var}" | sed 's/^ *//;s/ *$//'
}

normalise_secret_name() {
  local prefix="$1"
  local key="$2"
  local cleaned
  cleaned="$(echo "${key}" | tr '[:upper:]' '[:lower:]' | tr '_' '-')"
  echo "${prefix}-${cleaned}"
}

read_env_file() {
  local env_file="$1"
  while IFS= read -r line || [[ -n "${line}" ]]; do
    line="$(trim "${line%}")"
    [[ -z "${line}" || "${line}" == \#* ]] && continue
    if [[ "${line}" != *"="* ]]; then
      echo "[deploy] Skipping malformed line in ${env_file}: ${line}" >&2
      continue
    fi
    local key="${line%%=*}"
    local value="${line#*=}"
    key="$(trim "${key}")"
    value="$(trim "${value}")"
    if [[ -z "${key}" ]]; then
      echo "[deploy] Skipping empty key in ${env_file}" >&2
      continue
    fi
    printf '%s\t%s\n' "${key}" "${value}"
  done < "${env_file}"
}

ensure_services_enabled() {
  local apis=(
    "run.googleapis.com"
    "artifactregistry.googleapis.com"
    "cloudbuild.googleapis.com"
    "secretmanager.googleapis.com"
  )
  gcloud services enable "${apis[@]}" --project="${GCP_PROJECT_ID}" >/dev/null
}

ensure_artifact_repo() {
  if [[ -z "${ARTIFACT_REGISTRY_REPO:-}" ]]; then
    return
  fi
  if gcloud artifacts repositories describe "${ARTIFACT_REGISTRY_REPO}" \
      --location="${ARTIFACT_REGISTRY_LOCATION}" \
      --project="${GCP_PROJECT_ID}" >/dev/null 2>&1; then
    return
  fi
  echo "[deploy] Creating Artifact Registry repository ${ARTIFACT_REGISTRY_REPO}" >&2
  gcloud artifacts repositories create "${ARTIFACT_REGISTRY_REPO}" \
    --location="${ARTIFACT_REGISTRY_LOCATION}" \
    --project="${GCP_PROJECT_ID}" \
    --repository-format=docker \
    --description="Container images for PCA services"
}

configure_docker_auth() {
  local host="${ARTIFACT_REGISTRY_LOCATION}-docker.pkg.dev"
  gcloud auth configure-docker "${host}" --project="${GCP_PROJECT_ID}" --quiet >/dev/null
}

sync_secrets() {
  local env_file="$1"
  local prefix="$2"
  while IFS=$'\t' read -r key value; do
    local secret_name
    secret_name="$(normalise_secret_name "${prefix}" "${key}")"
    if [[ "${value}" =~ \$\{.*\} ]]; then
      echo "[deploy] Warning: ${key} in ${env_file} looks templated (contains \${}). Ensure Secret Manager holds the resolved value." >&2
    fi
    if ! gcloud secrets describe "${secret_name}" --project="${GCP_PROJECT_ID}" >/dev/null 2>&1; then
      printf '%s' "${value}" | gcloud secrets create "${secret_name}" \
        --project="${GCP_PROJECT_ID}" \
        --replication-policy=automatic \
        --data-file=- >/dev/null
    else
      printf '%s' "${value}" | gcloud secrets versions add "${secret_name}" \
        --project="${GCP_PROJECT_ID}" \
        --data-file=- >/dev/null
    fi
  done < <(read_env_file "${env_file}")
}

collect_secret_flags() {
  local env_file="$1"
  local prefix="$2"
  while IFS=$'\t' read -r key _; do
    local secret_name
    secret_name="$(normalise_secret_name "${prefix}" "${key}")"
    printf '%s\n' "${key}=${secret_name}:latest"
  done < <(read_env_file "${env_file}")
}

get_config_value() {
  local var_name="$1"
  if [[ -n "${!var_name-}" ]]; then
    echo "${!var_name}"
  fi
}

get_service_value() {
  local service="$1"
  local suffix="$2"
  local fallback_var="$3"
  local service_var
  service_var="${service^^}_${suffix}"
  if [[ -n "${!service_var-}" ]]; then
    echo "${!service_var}"
  elif [[ -n "${fallback_var}" && -n "${!fallback_var-}" ]]; then
    echo "${!fallback_var}"
  fi
}

build_image() {
  local service="$1"
  local dockerfile_rel="$2"
  local image_url="$3"
  local context_path="$4"
  echo "[deploy] Building ${service} image ${image_url}:${IMAGE_TAG}"

  local tmp_config
  tmp_config="$(mktemp)"
  if [[ -n "${DOCKER_HUB_USERNAME_SECRET:-}" && -n "${DOCKER_HUB_PASSWORD_SECRET:-}" ]]; then
    cat >"${tmp_config}" <<EOF
steps:
- name: 'gcr.io/cloud-builders/docker'
  entrypoint: 'bash'
  secretEnv: ['DOCKERHUB_USERNAME', 'DOCKERHUB_PASSWORD']
  args:
    - '-c'
    - |
        printf '%s' "$$DOCKERHUB_PASSWORD" | docker login -u "$$DOCKERHUB_USERNAME" --password-stdin
        docker build -t '${image_url}:${IMAGE_TAG}' -f '${dockerfile_rel}' .
images:
- '${image_url}:${IMAGE_TAG}'
availableSecrets:
  secretManager:
    - versionName: projects/${GCP_PROJECT_ID}/secrets/${DOCKER_HUB_USERNAME_SECRET}/versions/latest
      env: 'DOCKERHUB_USERNAME'
    - versionName: projects/${GCP_PROJECT_ID}/secrets/${DOCKER_HUB_PASSWORD_SECRET}/versions/latest
      env: 'DOCKERHUB_PASSWORD'
EOF
  else
    cat >"${tmp_config}" <<EOF
steps:
- name: 'gcr.io/cloud-builders/docker'
  args: ['build', '-t', '${image_url}:${IMAGE_TAG}', '-f', '${dockerfile_rel}', '.']
images:
- '${image_url}:${IMAGE_TAG}'
EOF
  fi

  gcloud builds submit "${context_path}" \
    --project="${GCP_PROJECT_ID}" \
    --config="${tmp_config}"

  rm -f "${tmp_config}"
}

deploy_service() {
  local service="$1"
  local service_name="$2"
  local image_url="$3"
  local env_file="$4"
  local secret_prefix="$5"
  local static_env_vars="$6"
  local port="$7"

  local region="${GCP_REGION}"
  local deploy_args=(
    "${service_name}"
    "--project=${GCP_PROJECT_ID}"
    "--region=${region}"
    "--image=${image_url}:${IMAGE_TAG}"
    "--platform=managed"
    "--port=${port}"
  )

  local cpu memory min_instances max_instances concurrency timeout ingress allow_unauth service_account vpc_connector vpc_egress
  cpu="$(get_service_value "${service}" "CPU" "CLOUD_RUN_CPU")"
  memory="$(get_service_value "${service}" "MEMORY" "CLOUD_RUN_MEMORY")"
  min_instances="$(get_service_value "${service}" "MIN_INSTANCES" "CLOUD_RUN_MIN_INSTANCES")"
  max_instances="$(get_service_value "${service}" "MAX_INSTANCES" "CLOUD_RUN_MAX_INSTANCES")"
  concurrency="$(get_service_value "${service}" "CONCURRENCY" "CLOUD_RUN_CONCURRENCY")"
  timeout="$(get_service_value "${service}" "TIMEOUT" "CLOUD_RUN_TIMEOUT")"
  ingress="$(get_service_value "${service}" "INGRESS" "CLOUD_RUN_INGRESS")"
  allow_unauth="$(get_service_value "${service}" "ALLOW_UNAUTHENTICATED" "CLOUD_RUN_ALLOW_UNAUTHENTICATED")"
  service_account="$(get_service_value "${service}" "SERVICE_ACCOUNT" "")"
  vpc_connector="$(get_service_value "${service}" "VPC_CONNECTOR" "")"
  vpc_egress="$(get_service_value "${service}" "VPC_EGRESS" "")"

  [[ -n "${cpu}" ]] && deploy_args+=("--cpu=${cpu}")
  [[ -n "${memory}" ]] && deploy_args+=("--memory=${memory}")
  [[ -n "${min_instances}" ]] && deploy_args+=("--min-instances=${min_instances}")
  [[ -n "${max_instances}" ]] && deploy_args+=("--max-instances=${max_instances}")
  [[ -n "${concurrency}" ]] && deploy_args+=("--concurrency=${concurrency}")
  [[ -n "${timeout}" ]] && deploy_args+=("--timeout=${timeout}")
  [[ -n "${ingress}" ]] && deploy_args+=("--ingress=${ingress}")
  if [[ -n "${allow_unauth}" ]]; then
    if [[ "${allow_unauth}" == "true" ]]; then
      deploy_args+=("--allow-unauthenticated")
    else
      deploy_args+=("--no-allow-unauthenticated")
    fi
  fi
  [[ -n "${service_account}" ]] && deploy_args+=("--service-account=${service_account}")
  if [[ -n "${vpc_connector}" ]]; then
    deploy_args+=("--vpc-connector=${vpc_connector}")
    [[ -n "${vpc_egress}" ]] && deploy_args+=("--vpc-egress=${vpc_egress}")
  fi

  mapfile -t secret_entries < <(collect_secret_flags "${env_file}" "${secret_prefix}")
  if ((${#secret_entries[@]})); then
    local secret_flag
    secret_flag=$(IFS=,; echo "${secret_entries[*]}")
    deploy_args+=("--set-secrets=${secret_flag}")
  fi

  if [[ -n "${static_env_vars}" ]]; then
    deploy_args+=("--set-env-vars=${static_env_vars}")
  fi

  echo "[deploy] Deploying ${service_name} to Cloud Run"
  gcloud run deploy "${deploy_args[@]}"
}

main() {
  require_config GCP_PROJECT_ID
  require_config GCP_REGION
  require_config ARTIFACT_REGISTRY_REPO
  require_config ARTIFACT_REGISTRY_LOCATION
  require_config API_SERVICE_NAME
  require_config FRONTEND_SERVICE_NAME
  require_config API_IMAGE_URL
  require_config FRONTEND_IMAGE_URL
  require_config API_ENV_FILE
  require_config FRONTEND_ENV_FILE
  require_config API_SECRET_PREFIX
  require_config FRONTEND_SECRET_PREFIX
  require_config API_PORT
  require_config FRONTEND_PORT
  require_config API_DOCKERFILE
  require_config FRONTEND_DOCKERFILE

  ensure_services_enabled
  ensure_artifact_repo
  configure_docker_auth

  for service in "${SERVICES[@]}"; do
    case "${service}" in
      api)
        local api_env_path
        api_env_path="$(resolve_path "${API_ENV_FILE}")"
        ensure_env_file "${api_env_path}"
        sync_secrets "${api_env_path}" "${API_SECRET_PREFIX}"
        local api_dockerfile_path
        api_dockerfile_path="$(resolve_path "${API_DOCKERFILE}")"
        if [[ ! -f "${api_dockerfile_path}" ]]; then
          echo "[deploy] Dockerfile not found: ${api_dockerfile_path}" >&2
          exit 1
        fi
        local api_dockerfile_rel
        api_dockerfile_rel="$(relative_to_project_root "${api_dockerfile_path}")"
        build_image "api" "${api_dockerfile_rel}" "${API_IMAGE_URL}" "${PROJECT_ROOT}"
        deploy_service "api" "${API_SERVICE_NAME}" "${API_IMAGE_URL}" "${api_env_path}" "${API_SECRET_PREFIX}" "${API_STATIC_ENV_VARS}" "${API_PORT}"
        ;;
      frontend)
        local frontend_env_path
        frontend_env_path="$(resolve_path "${FRONTEND_ENV_FILE}")"
        ensure_env_file "${frontend_env_path}"
        sync_secrets "${frontend_env_path}" "${FRONTEND_SECRET_PREFIX}"
        local frontend_dockerfile_path
        frontend_dockerfile_path="$(resolve_path "${FRONTEND_DOCKERFILE}")"
        if [[ ! -f "${frontend_dockerfile_path}" ]]; then
          echo "[deploy] Dockerfile not found: ${frontend_dockerfile_path}" >&2
          exit 1
        fi
        local frontend_dockerfile_rel
        frontend_dockerfile_rel="$(relative_to_project_root "${frontend_dockerfile_path}")"
        build_image "frontend" "${frontend_dockerfile_rel}" "${FRONTEND_IMAGE_URL}" "${PROJECT_ROOT}"
        deploy_service "frontend" "${FRONTEND_SERVICE_NAME}" "${FRONTEND_IMAGE_URL}" "${frontend_env_path}" "${FRONTEND_SECRET_PREFIX}" "${FRONTEND_STATIC_ENV_VARS}" "${FRONTEND_PORT}"
        ;;
    esac
  done

  echo "[deploy] Completed. Active revision tags use image tag ${IMAGE_TAG}."
}

main "$@"
