# Deployment Infrastructure & Orchestration

UrbanFlow supports multiple deployment topologies ranging from local Docker Compose environments to local Kubernetes (Kind) and production AWS staging stacks.

```
deploy/
├── helm/urbanflow/           # Umbrella Helm chart (backend, frontend, worker, ingest subcharts)
├── helm/values-kind.yaml     # Values overrides for local Kind cluster (NodePort 30080, emptyDir)
├── kind/kind-config.yaml     # Kind cluster definition mapping host port 127.0.0.1:8080 to node 30080
├── autoscaling/              # KEDA ScaledObject and Cluster Autoscaler spot configurations
├── chaos/                    # Chaos engineering scripts: network latency and container restart probes
├── k6/                       # k6 load, smoke, and spike performance test scripts
├── observability/            # Prometheus configuration, alert rules, and Grafana dashboard models
└── scripts/smoke-test.sh     # Shell smoke-test script verifying /health and API endpoints
```

---

## 1. Local Kubernetes Deployment via Kind & Helm

Prerequisites: Docker Engine, [kind](https://kind.sigs.k8s.io/), `kubectl`, and Helm 3.

```bash
# 1. Build local container images (from repository root)
docker build -f backend/Dockerfile -t urbanflow-backend:dev --build-arg GIT_COMMIT=$(git rev-parse HEAD) .
docker build -f frontend/Dockerfile -t urbanflow-frontend:dev ./frontend

# 2. Create Kind cluster and preload images
kind create cluster --name urbanflow --config deploy/kind/kind-config.yaml
kind load docker-image urbanflow-backend:dev urbanflow-frontend:dev --name urbanflow

# 3. Deploy umbrella Helm chart
helm upgrade --install urbanflow deploy/helm/urbanflow -f deploy/helm/values-kind.yaml --wait --timeout 8m

# 4. Verify deployment via automated smoke test
bash deploy/scripts/smoke-test.sh http://127.0.0.1:8080

# 5. Teardown
helm uninstall urbanflow
kind delete cluster --name urbanflow
```

Optional Go Ingest Service (F1):
```bash
docker build -f services/ingest-go/Dockerfile -t urbanflow-ingest:dev .
kind load docker-image urbanflow-ingest:dev --name urbanflow
helm upgrade --install urbanflow deploy/helm/urbanflow -f deploy/helm/values-kind.yaml --set ingest.enabled=true --wait
```

---

## 2. Asynchronous Job Worker & Autoscaling

The background simulation worker processes heavy multi-seed studies from an SQS queue. In Kubernetes, the worker scales based on SQS queue depth via KEDA:
- See [`deploy/autoscaling/README.md`](autoscaling/README.md) for KEDA `ScaledObject` and spot instance configuration.
- The worker deployment tolerates spot taints (`spot=true:NoSchedule`) and selects batch nodes, ensuring idle queues consume zero compute.

---

## 3. Observability, Load & Chaos Testing

- **Telemetry & Alerts:** [`deploy/observability/`](observability/) holds Prometheus scrape configs, alert rules, and Grafana dashboards for latency, run throughput, and queue depth.
- **k6 Load Tests:** [`deploy/k6/README.md`](k6/README.md) contains performance test scripts measuring p95 endpoint latencies under concurrent traffic.
- **Chaos Injection:** [`deploy/chaos/README.md`](chaos/README.md) contains Python probes that test system resilience against backend restarts and network degradation.

---

## 4. AWS Staging Stack (Terraform)

For deploying the production stack to Amazon Web Services (EKS, RDS PostgreSQL, S3, SQS, IAM OIDC), refer to [`infra/terraform/README.md`](../infra/terraform/README.md).
