# MediLink on Kubernetes

This is a local-learning Kubernetes deployment for MediLink. It keeps the existing Django modular monolith and deploys PostgreSQL, Redis, Django API, Celery worker, Celery Beat, and React/Nginx frontend separately.

## Build images

From the repository root:

```powershell
docker build -t medilink-backend:local ./backend
docker build --build-arg REACT_APP_API_URL=/api -t medilink-frontend:local ./frontend
```

If Kubernetes cannot access the local Docker image store, push the images to a registry and update image names in `k8s/app.yaml`.

## Deploy locally

1. Copy `k8s/.env.example` to `k8s/.env`, then replace the values. Never commit `k8s/.env`.
2. Create namespace, Secret and ConfigMap:

```powershell
kubectl create namespace medilink --dry-run=client -o yaml | kubectl apply -f -
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

4. Deploy workloads:

```powershell
kubectl apply -f k8s/app.yaml
kubectl rollout status job/backend-migrate -n medilink --timeout=300s
kubectl rollout status deployment/backend -n medilink --timeout=180s
kubectl rollout status deployment/celery-worker -n medilink --timeout=180s
kubectl rollout status deployment/celery-beat -n medilink --timeout=180s
kubectl rollout status deployment/frontend -n medilink --timeout=180s
kubectl get pods,svc,pvc -n medilink
```

5. Start a port-forward:

```powershell
kubectl port-forward -n medilink service/frontend 3000:80
```

Open http://localhost:3000. To access API-only endpoints in a separate terminal, run `kubectl port-forward -n medilink service/backend 8000:8000`.

6. Seed demo data only when you need it:

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

- This is a learning setup, not a production healthcare deployment.
- A PVC is not a backup; configure and test backups and restores before storing important data.
- Local image availability and storage classes vary by cluster.
- Schema migration runs as a Kubernetes Job instead of racing from every API replica. For production releases, run a controlled pre-deploy migration step and use backward-compatible migrations.
- Static assets are collected by the migration Job into its own ephemeral filesystem. Verify the static-file serving path for your environment; for production, use an explicit shared/object-storage strategy for static assets and media. Media uploads are not persisted by these manifests.
- PostgreSQL and Redis are single instances; no HA is configured.
- Before production, add TLS/Ingress, managed secrets, network policies, Pod security controls, resource sizing, database connection pooling, monitoring, and tested recovery.
- Do not use demo credentials or sample secrets in a real deployment.
