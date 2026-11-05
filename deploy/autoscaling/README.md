# Autoscaling and spot capacity (F17, package 2E)

Status: **WRITTEN, not applied.** Helm and kubectl were not available when this was written, so none of it has been
rendered, linted or applied to a cluster.

Two layers scale independently:

| Layer | What scales | Driven by | Provisioned by |
|---|---|---|---|
| Pods | `worker` Deployment, 0 to `keda.maxReplicaCount` | SQS queue depth | KEDA `ScaledObject` (worker chart `keda.enabled`) |
| Nodes | managed node group `spot-batch`, 0 to `spot_max_size` | pending pods | cluster autoscaler (or Karpenter, see below) |

The spot group is tainted `spot=true:NoSchedule` and labelled `workload=batch`; the worker chart tolerates the taint
and selects the label, so the always-on services (API, frontend) never land on spot nodes and an idle queue costs no
batch compute.

## Install order (once per cluster)

1. Terraform applied (`infra/terraform/README.md`), namespace `urbanflow` created.
2. KEDA: `helm repo add kedacore https://kedacore.github.io/charts` then
   `helm upgrade --install keda kedacore/keda -n keda --create-namespace`.
3. Cluster autoscaler: `cluster-autoscaler-values.yaml` (needs an IRSA role this repository does not create yet).
4. UrbanFlow with the worker on:
   `helm upgrade --install urbanflow deploy/helm/urbanflow -n urbanflow --set worker.enabled=true --set worker.keda.enabled=true`
   plus the queue url, DLQ url, bucket, role ARN and owner from the Terraform outputs.

## Files

- `keda-scaledobject.example.yaml`: the KEDA objects as plain manifests (the chart renders the same).
- `cluster-autoscaler-values.yaml`: Helm values for the cluster autoscaler chart.
- `karpenter-nodepool.example.yaml`: Karpenter spot NodePool as an alternative to the managed group. Pick one of
  the two node scalers, not both.

## Open points

- The KEDA trigger uses `identityOwner: workload`, i.e. the worker's own IRSA role. This is the documented pattern for
  the `aws` pod identity provider but has not been exercised here; if it fails, give the KEDA operator its own role
  with `sqs:GetQueueAttributes` on the job queue and use `identityOwner: operator`.
- Spot interruptions: a reclaimed node sends SIGTERM; the worker finishes the job in hand if it can, otherwise the
  visibility timeout returns the job to the queue and another worker runs it (the run store makes that safe).
  Install the AWS Node Termination Handler or use Karpenter's interruption queue to get the two-minute warning.
- The F17 "budget cap stops new jobs" rule is application logic, not infrastructure: see `infra/terraform/README.md`.
