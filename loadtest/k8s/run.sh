#!/usr/bin/env bash
# Stepped capacity test of MediLink, run inside the Kubernetes cluster.
#
#   loadtest/k8s/run.sh                       # ramp toward 100,000 users, stop when saturated
#   WORKERS=6 RUN=scaled loadtest/k8s/run.sh  # more load generators, named run
#   STEP_USERS=50,100 STEP_HOLD_SECONDS=20 loadtest/k8s/run.sh   # quick smoke run
#
# Reports land in loadtest/reports/<RUN>/: steps.csv (one row per step),
# report.html (Locust's report), run_*.csv, and cluster-cpu.log (per-container
# CPU samples from the kind node, when it is a kind cluster).
# Remove everything afterwards with:  kubectl delete namespace loadtest
set -euo pipefail
export MSYS_NO_PATHCONV=1   # Git Bash on Windows: don't rewrite /reports etc.

cd "$(dirname "$0")/.."
RUN=${RUN:-k8s-$(date +%Y%m%d-%H%M%S)}
WORKERS=${WORKERS:-4}
NS=loadtest
OUT=reports/$RUN
KIND_NODE=${KIND_NODE:-medilink-control-plane}
mkdir -p "$OUT"

ingress_ip=$(kubectl -n ingress-nginx get svc ingress-nginx-controller -o jsonpath='{.spec.clusterIP}')
echo "run=$RUN workers=$WORKERS ingress=$ingress_ip"

# Fresh master for every run; workers restart so they reconnect to it
kubectl -n "$NS" delete job locust-master --ignore-not-found --wait=true >/dev/null 2>&1 || true
kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f - >/dev/null

kubectl -n "$NS" create configmap locustfiles \
  --from-file=locustfile.py --from-file=shape_stepped.py \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null

settings=(--from-literal=WORKERS="$WORKERS" --from-literal=LOCUST_EXTRA_ARGS="${LOCUST_EXTRA_ARGS:-}")
for var in STEP_USERS STEP_MAX_USERS STEP_HOLD_SECONDS STEP_RAMP_SECONDS STEP_MAX_FAIL_RATIO STEP_MAX_P95_MS \
           MEDILINK_THINK_MIN MEDILINK_THINK_MAX; do
  [[ -n "${!var:-}" ]] && settings+=(--from-literal="$var=${!var}")
done
kubectl -n "$NS" create configmap locust-settings "${settings[@]}" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null

# Start order matters, both ways round:
#  - a worker killed after it connected (e.g. by a restart) makes the master end the run;
#  - a worker that starts before the master exists can sit on a dead connection
#    to the Service for minutes and never join.
# So: no workers, then a ready master, then fresh workers (which also load the
# current locustfiles).
sed "s/INGRESS_IP/$ingress_ip/" k8s/locust.yaml | kubectl apply -f - >/dev/null
kubectl -n "$NS" scale deploy/locust-worker --replicas=0 >/dev/null
kubectl -n "$NS" wait --for=delete pod -l app=locust-worker --timeout=120s >/dev/null 2>&1 || true

kubectl apply -f k8s/master.yaml >/dev/null
kubectl -n "$NS" wait --for=condition=ready pod -l app=locust-master --timeout=180s >/dev/null

kubectl -n "$NS" scale deploy/locust-worker --replicas="$WORKERS" >/dev/null
kubectl -n "$NS" rollout status deploy/locust-worker --timeout=180s >/dev/null
master=$(kubectl -n "$NS" get pod -l app=locust-master -o jsonpath='{.items[0].metadata.name}')
echo "master=$master  (follow with: kubectl -n $NS logs -f $master)"

# Sample per-container CPU on the kind node while the test runs
sampler=""
if docker inspect "$KIND_NODE" >/dev/null 2>&1; then
  ( while true; do
      echo "== $(date +%T)"
      docker exec "$KIND_NODE" crictl stats 2>/dev/null | sed 's/\x1b\[[0-9;]*[A-Za-z]//g'
      sleep 10
    done ) > "$OUT/cluster-cpu.log" 2>&1 &
  sampler=$!
fi

# Show each finished step as it happens, until the master signals it is done
seen=0
until kubectl -n "$NS" exec "$master" -- test -f /reports/DONE 2>/dev/null; do
  lines=$(kubectl -n "$NS" logs "$master" 2>/dev/null | grep -E "STEP users=|STOP:" || true)
  count=$(printf "%s" "$lines" | grep -c . || true)
  if (( count > seen )); then printf "%s\n" "$lines" | tail -n $((count - seen)) | sed 's/^.*\(STEP\|STOP\)/\1/'; seen=$count; fi
  sleep 10
done
[[ -n "$sampler" ]] && kill "$sampler" 2>/dev/null || true

kubectl -n "$NS" logs "$master" > "$OUT/master.log"
for f in steps.csv report.html run_stats.csv run_failures.csv run_exceptions.csv run_stats_history.csv; do
  kubectl -n "$NS" cp "$master:/reports/$f" "$OUT/$f" >/dev/null 2>&1 || true
done
grep -E "Stepped run finished|LOCUST_EXIT" "$OUT/master.log" || true
echo "reports: loadtest/$OUT"
column -s, -t < "$OUT/steps.csv" 2>/dev/null || cat "$OUT/steps.csv"
