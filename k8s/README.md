# MediLink on Kubernetes

This is a local-learning Kubernetes deployment for MediLink. It keeps the Django modular monolith and deploys PostgreSQL, Redis, Django API, Celery worker, Celery Beat, and React/Nginx frontend separately.

## Build images

From the repository root:

```powershell
docker build -t medilink-backend:local ./backend
docker build --build-arg REACT_APP_API_URL=/api -t medilink-frontend:local ./frontend
```

The backend image collects Django static assets at build time so every API Pod has its own copy. If the cluster cannot access Docker Desktop's image store, push the images to a registry and update image names in `k8s/app.yaml`.

## Deploy locally

1. Copy `k8s/.env.example` to `k8s/.env`, edit the values, and never commit `k8s/.env`.
2. Create namespace, Secret and ConfigMap:

```powershell
kubectl apply -f k8s/namespace.yaml
kubectl -n medilink create secret generic medilink-secrets --from-env-file=k8s/.env --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f k8s/configmap.yaml
```

3. Deploy PostgreSQL and Redis:

```powershell
kubectl apply -f k8s/postgres.yaml
kubectl rollout status statefulset/postgres -n medilink --timeout=180s
kubectl apply -f k8s/redis.yaml
kubectl rollout status deployment/redis -n medilink --timeout=120s
```

4. Deploy application workloads:

```powershell
kubectl apply -f k8s/migration-job.yaml
kubectl rollout status job/backend-migrate -n medilink --timeout=300s
kubectl apply -f k8s/app.yaml
kubectl rollout status deployment/backend -n medilink --timeout=180s
kubectl rollout status deployment/celery-worker -n medilink --timeout=180s
kubectl rollout status deployment/celery-beat -n medilink --timeout=180s
kubectl rollout status deployment/frontend -n medilink --timeout=180s
kubectl get pods,svc,pvc -n medilink
```

5. Open the frontend:

```powershell
kubectl port-forward -n medilink service/frontend 3000:80
```

Browse to http://localhost:3000. Optionally expose API-only endpoints in another terminal with `kubectl port-forward -n medilink service/backend 8000:8000`.

6. Seed demonstration data only when needed:

```powershell
kubectl exec -n medilink deployment/backend -- python manage.py seed_demo_data
```

## Troubleshooting

```powershell
kubectl get pods -n medilink
kubectl describe pod <pod-name> -n medilink
kubectl logs deployment/backend -n medilink
kubectl logs deployment/backend -n medilink --previous
kubectl get events -n medilink --sort-by=.metadata.creationTimestamp
```

## Scope and production gaps

- This is a local development and learning setup, not a production healthcare deployment.
- A PVC is not a backup; configure and test backups and restores before storing important data.
- Local image availability and storage classes vary by cluster.
- Schema migration runs as a Kubernetes Job rather than racing from every API replica. For production releases, use a controlled pre-deploy migration step and backward-compatible migrations.
- Media uploads are not persisted by these manifests. Use durable object storage or a deliberately configured shared volume before relying on uploads.
- PostgreSQL and Redis are single instances; no HA is configured.
- Before production, add TLS/Ingress, managed secrets, network policies, Pod security controls, resource sizing, database connection pooling, monitoring, and tested recovery.
- Do not use demo credentials or sample secrets in a real deployment.
