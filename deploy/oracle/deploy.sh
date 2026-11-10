#!/usr/bin/env bash
# Deploy (or upgrade) MediLink onto the k3s cluster.
#
#   MEDILINK_HOST=medilink.<public-ip>.sslip.io bash deploy/oracle/deploy.sh
#
# Optional env:
#   IMAGE_TAG=<git sha>        deploy a specific image tag (default: latest)
#   ANTHROPIC_API_KEY=sk-...   enable the Claude-powered agents
#   SEED_DEMO_DATA=1           load the demo accounts after deploying
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OVERLAY="$ROOT/deploy/k8s/overlays/oracle"
export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"

# params.env: public hostname
if [[ -n "${MEDILINK_HOST:-}" ]]; then
  echo "HOST=${MEDILINK_HOST}" > "$OVERLAY/params.env"
elif [[ ! -f "$OVERLAY/params.env" ]]; then
  echo "Set MEDILINK_HOST (e.g. medilink.\$(curl -s ifconfig.me).sslip.io) or create $OVERLAY/params.env" >&2
  exit 1
fi

# secrets.env: generated once, then reused so the DB password never changes
if [[ ! -f "$OVERLAY/secrets.env" ]]; then
  echo "==> Generating $OVERLAY/secrets.env (keep it safe; it is git-ignored)"
  gen() { python3 -c "import secrets; print(secrets.token_urlsafe(48))"; }
  umask 077
  cat > "$OVERLAY/secrets.env" <<EOF
SECRET_KEY=$(gen)
DB_PASSWORD=$(gen)
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
EOF
elif [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
  sed -i "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}|" "$OVERLAY/secrets.env"
fi

TAG="${IMAGE_TAG:-latest}"
echo "==> Applying manifests (image tag: $TAG)"
kubectl kustomize "$OVERLAY" \
  | sed -E "s#(ghcr.io/[^/]+/medilink-(backend|frontend)):latest#\1:${TAG}#g" \
  | kubectl apply -f -

echo "==> Waiting for rollouts"
kubectl -n medilink rollout status statefulset/postgres --timeout=300s
for d in redis backend celery-worker celery-beat frontend; do
  kubectl -n medilink rollout status "deploy/$d" --timeout=600s
done
# Pick up config changes (the ConfigMap isn't hashed)
kubectl -n medilink rollout restart deploy/backend deploy/celery-worker deploy/celery-beat >/dev/null

if [[ "${SEED_DEMO_DATA:-0}" == "1" ]]; then
  echo "==> Seeding demo data"
  kubectl -n medilink rollout status deploy/backend --timeout=600s
  kubectl -n medilink exec deploy/backend -- python manage.py seed_demo_data
fi

HOST=$(grep '^HOST=' "$OVERLAY/params.env" | cut -d= -f2)
echo
echo "✅ MediLink is deploying at https://${HOST}"
echo "   TLS certificate status: kubectl -n medilink get certificate"
