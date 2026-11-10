#!/usr/bin/env bash
# One-time setup of a single-node Kubernetes (k3s) cluster on an Oracle Cloud
# "Always Free" Ampere A1 VM (Ubuntu 22.04/24.04, arm64). Run ON the VM:
#
#   LETSENCRYPT_EMAIL=you@example.com sudo -E bash bootstrap-k3s.sh
#
# What it does:
#   1. Opens ports 80/443 in the VM's host firewall (Oracle's Ubuntu images
#      ship iptables rules that REJECT everything except SSH).
#   2. Installs k3s (Kubernetes + Traefik ingress + local-path storage).
#   3. Installs cert-manager and a Let's Encrypt ClusterIssuer for free TLS.
set -euo pipefail

if [[ -z "${LETSENCRYPT_EMAIL:-}" ]]; then
  echo "Set LETSENCRYPT_EMAIL (used by Let's Encrypt for certificate expiry notices)" >&2
  exit 1
fi
K3S_VERSION="${K3S_VERSION:-v1.31.4+k3s1}"
CERT_MANAGER_VERSION="${CERT_MANAGER_VERSION:-v1.16.2}"

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root (sudo -E bash $0)" >&2
  exit 1
fi

echo "==> [1/4] Opening HTTP/HTTPS in the host firewall"
for port in 80 443; do
  if ! iptables -C INPUT -p tcp -m state --state NEW --dport "$port" -j ACCEPT 2>/dev/null; then
    # Insert before Oracle's default REJECT rule
    iptables -I INPUT 6 -p tcp -m state --state NEW --dport "$port" -j ACCEPT
  fi
done
if command -v netfilter-persistent >/dev/null 2>&1; then
  netfilter-persistent save
fi

echo "==> [2/4] Installing k3s ${K3S_VERSION}"
if ! command -v k3s >/dev/null 2>&1; then
  curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="$K3S_VERSION" sh -s - --write-kubeconfig-mode 644
fi
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
until kubectl get nodes >/dev/null 2>&1; do sleep 3; done
kubectl wait --for=condition=Ready node --all --timeout=180s

echo "==> [3/4] Installing cert-manager ${CERT_MANAGER_VERSION}"
kubectl apply -f "https://github.com/cert-manager/cert-manager/releases/download/${CERT_MANAGER_VERSION}/cert-manager.yaml"
kubectl -n cert-manager rollout status deploy/cert-manager-webhook --timeout=300s

echo "==> [4/4] Creating the Let's Encrypt ClusterIssuer"
ISSUER_FILE="$(mktemp)"
cat > "$ISSUER_FILE" <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: ${LETSENCRYPT_EMAIL}
    privateKeySecretRef:
      name: letsencrypt-prod-account
    solvers:
      - http01:
          ingress:
            ingressClassName: traefik
EOF
# Retry: the webhook can take a few seconds to accept requests after rollout
for i in $(seq 1 20); do
  if kubectl apply -f "$ISSUER_FILE"; then
    break
  fi
  echo "   cert-manager webhook not ready yet, retrying ($i)..."
  sleep 6
done
rm -f "$ISSUER_FILE"

cat <<'MSG'

✅ k3s is ready.
Next:
  1. In the Oracle Cloud console, allow TCP 80 and 443 in the VCN Security List
     (Networking → Virtual Cloud Networks → your VCN → Security Lists → Add Ingress Rules,
      source 0.0.0.0/0).
  2. Copy the kubeconfig to your laptop if you want to deploy remotely:
       sudo cat /etc/rancher/k3s/k3s.yaml   (replace 127.0.0.1 with the VM's public IP
       and open TCP 6443 only to your own IP)
  3. Deploy MediLink:  bash deploy/oracle/deploy.sh
MSG
