# O2 — Control-Plane Connectivity Interruption

## 1. Objective

The objective of O2 is to demonstrate workload resilience when an edge worker node temporarily loses connectivity to the Kubernetes control plane.

The experiment evaluates:

- Node health
- Kubernetes API connectivity
- Workload availability
- Service endpoint continuity
- Traffic continuity
- Guardian monitoring
- Workload recovery after fault removal

---

## 2. Environment

### Kubernetes Cluster

| Component | Value |
|---|---|
| Kubernetes distribution | K3s |
| Kubernetes version | v1.35.5+k3s1 |
| Cluster | k3d-cloud138 |
| Control plane | k3d-cloud138-server-0 |
| Worker 1 | k3d-cloud138-agent-0 |
| Worker 2 | k3d-cloud138-agent-1 |

### Network

| Component | Address |
|---|---|
| Control plane | 172.18.0.3 |
| Agent-0 | 172.18.0.4 |
| Agent-1 | 172.18.0.5 |
| Kubernetes API | 172.18.0.3:6443 |

---

## 3. Workload

Namespace:

`edge-lab`

Deployment:

`edge-workload`

Replicas:

`2`

Container image:

`nginx:alpine`

Service:

`edge-workload`

Service type:

`ClusterIP`

Service port:

`80`

The workload is distributed across the worker nodes.

---

## 4. Monitoring

The project contains two monitoring components.

### Edge Guardian

The Guardian runs outside the cluster and monitors:

- Kubernetes API availability
- Deployment health
- Node readiness

Possible states include:

- `NORMAL`
- `DEGRADED`
- `NODE_DEGRADED`
- `WORKLOAD_FAILURE`

### Edge Probe

The Edge Probe runs inside the cluster on:

`k3d-cloud138-agent-0`

It continuously checks connectivity to:

`kubernetes.default.svc:443`

The probe records API reachability and connection time.

---

# 5. Baseline

Before fault injection, the cluster was healthy.

The baseline deployment showed:

`edge-workload 2/2`

The service was available through:

`ClusterIP 10.43.17.190`

The EndpointSlice contained both workload endpoints:

- `10.42.2.5`
- `10.42.3.4`

Both workload pods were running.

Normal traffic returned:

`HTTP 200`

The Guardian reported:

`API=HEALTHY`

`WORKLOAD=HEALTHY (2/2)`

`STATE=NORMAL`

---

# 6. Fault Injection

The fault was introduced on:

`k3d-cloud138-agent-0`

The worker's connectivity to the Kubernetes control plane was blocked using:

```text
iptables