# Deploy: Helm chart and local kind cluster

No cloud account is needed. Prerequisites: Docker, [kind](https://kind.sigs.k8s.io/), kubectl, Helm 3.

```
deploy/
  helm/urbanflow/           umbrella chart (subcharts: backend, frontend, ingest)
  helm/values-kind.yaml     overrides for kind (NodePort 30080, no PVC)
  kind/kind-config.yaml     cluster config: host 127.0.0.1:8080 -> node 30080
  scripts/smoke-test.sh     curl checks used by CI and by hand
```

## Runbook

```bash
# 1. Images (from the repository root)
docker build -f backend/Dockerfile -t urbanflow-backend:dev --build-arg GIT_COMMIT=$(git rev-parse HEAD) .
docker build -f frontend/Dockerfile -t urbanflow-frontend:dev ./frontend

# 2. Cluster and image load
kind create cluster --name urbanflow --config deploy/kind/kind-config.yaml
kind load docker-image urbanflow-backend:dev urbanflow-frontend:dev --name urbanflow

# 3. Install
helm upgrade --install urbanflow deploy/helm/urbanflow -f deploy/helm/values-kind.yaml --wait --timeout 8m

# 4. Check
bash deploy/scripts/smoke-test.sh http://127.0.0.1:8080

# Tear down
helm uninstall urbanflow
kind delete cluster --name urbanflow
```

Optional Go ingest service (F1): build `urbanflow-ingest:dev` with
`docker build -f services/ingest-go/Dockerfile -t urbanflow-ingest:dev .`, `kind load` it, and add
`--set ingest.enabled=true` to the install.

## Notes

- The frontend nginx config proxies to the hostname `backend`, so the backend Service is named `backend`
  (`backend.service.name`). Change both together or neither.
- The backend uses a SQLite file, so it runs as a single replica with a `Recreate` strategy. On kind the
  volume is an `emptyDir` (data is lost when the pod is recreated); remove `backend.persistence.enabled=false`
  from `values-kind.yaml` to use a PVC.
- `backend.env.TRUSTED_PROXY_IPS` must cover the pod network so the backend believes nginx's `X-Real-IP`
  (kind default pod CIDR `10.244.0.0/16`).
- Set `backend.apiKey` and `frontend.apiKey` to the same value to enable API-key auth, or point
  `existingSecret` at a Secret with keys `API_KEY`, `METRICS_TOKEN` (backend) and `BACKEND_API_KEY` (frontend).
- CI: `.github/workflows/k8s-deploy.yml` does the same steps on a throwaway kind cluster.

More operations detail: `docs/operations-platform.md`.
