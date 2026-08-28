# CLOUD-138 — Edge Resilience and Guardian Monitoring

## 1. Project Overview

CLOUD-138 is a Kubernetes-based edge resilience experiment designed to demonstrate workload continuity during node-level control-plane connectivity interruption.

The project deploys a two-replica edge workload across multiple Kubernetes nodes and uses an Edge Guardian to monitor:

- Kubernetes API availability
- Workload health
- Node readiness
- Overall system state

The experiment intentionally interrupts Kubernetes API connectivity from one edge node to the control-plane node and observes the resulting node degradation, workload continuity, rescheduling, and recovery.

---

## 2. Environment

### Kubernetes Cluster

The experiment uses a k3d-managed K3s cluster containing:

| Node | Role |
|---|---|
| k3d-cloud138-server-0 | Control plane |
| k3d-cloud138-agent-0 | Edge worker |
| k3d-cloud138-agent-1 | Edge worker |

Kubernetes version used during the experiment:

1.35.5+k3s1

---

## 3. Edge Workload

The workload is deployed in the edge-lab namespace.

Deployment:

edge-workload

Replicas:

2

Container image:


ginx:alpine

Resources:

- CPU request: 50m
- Memory request: 32Mi
- CPU limit: 200m
- Memory limit: 64Mi

The workload is exposed through a Kubernetes ClusterIP Service on port 80.

The two workload replicas initially run on different edge nodes.

---

## 4. Connectivity Test

A continuous connectivity-test pod sends HTTP requests to:

edge-workload.edge-lab.svc.cluster.local

The test runs continuously and records:

- HTTP status code
- Request response time

Normal operation produces HTTP 200 responses.

---

## 5. Edge Guardian

The Guardian is a Python-based read-only monitoring component.

Location:

guardian/guardian.py

Configuration:

guardian/config.yaml

The Guardian monitors:

1. Kubernetes API health
2. Deployment health
3. Node readiness

It classifies the system into states such as:

- NORMAL
- DEGRADED
- NODE_DEGRADED
- WORKLOAD_FAILURE

The Guardian checks the cluster every 5 seconds.

---

## 6. Edge Probe

The project also contains an edge-local API connectivity probe.

Location:

guardian/probe/

The probe runs directly on:

k3d-cloud138-agent-0

It checks connectivity to:

kubernetes.default.svc:443

and records API reachability and connection time.

---

# 7. Experiment O2 — Control-Plane Connectivity Interruption

## Objective

Determine whether an edge node can lose connectivity to the Kubernetes control plane while the application workload continues to serve traffic.

The experiment consists of:

1. Baseline measurement
2. Fault injection
3. Fault observation
4. Guardian detection
5. Workload continuity
6. Workload rescheduling
7. Fault recovery
8. Guardian recovery verification

---

## 8. Baseline

Before fault injection:

- All three nodes were Ready.
- edge-workload had 2/2 replicas available.
- Two workload endpoints were present.
- Continuous connectivity returned HTTP 200.

Baseline evidence is stored in:

experiments/O2-baseline/

---

## 9. Fault Injection

The fault was introduced on:

k3d-cloud138-agent-0

The node's outbound TCP connectivity to the Kubernetes API server was blocked:

172.18.0.3:6443

using an iptables REJECT rule.

This simulates interruption of control-plane connectivity from an edge worker.

---

## 10. Observed Fault

During the experiment:

k3d-cloud138-agent-0 became:

NotReady

while:

k3d-cloud138-agent-1 remained Ready

and:

k3d-cloud138-server-0 remained Ready.

The fault evidence is stored in:

experiments/O2-control-plane-interruption/

---

## 11. Workload Resilience

During the node degradation:

- The workload replica on agent-0 entered termination.
- Kubernetes created a replacement replica.
- The replacement workload was scheduled on the control-plane node.
- The deployment returned to 2/2 available replicas.

The surviving workload on agent-1 continued serving traffic.

The connectivity test continued returning HTTP 200 responses.

This demonstrates application-level continuity despite node degradation.

---

## 12. Guardian Detection

During the fault, the Guardian reported:

API=HEALTHY

WORKLOAD=HEALTHY (2/2)

STATE=NODE_DEGRADED

and identified:

k3d-cloud138-agent-0 -> NotReady

while the other nodes remained Ready.

Evidence:

experiments/O2-control-plane-interruption/guardian-v3-during-fault.txt

---

## 13. Recovery

After the experiment, the iptables rule was removed.

The affected node returned to:

Ready

The workload stabilized at:

2/2

Continuous HTTP connectivity continued returning:

HTTP 200

The Guardian subsequently reported:

API=HEALTHY | WORKLOAD=HEALTHY (2/2) | STATE=NORMAL

with all three nodes Ready.

Recovery evidence is stored in:

experiments/O2-control-plane-interruption/final/

---

# 14. Experiment Result

The O2 experiment demonstrated the following sequence:

`	ext
Normal Operation
       |
       v
Inject Control-Plane Connectivity Fault
       |
       v
Agent-0 -> NotReady
       |
       +--------------------+
       |                    |
       v                    v
Guardian detects       Workload continues
NODE_DEGRADED          serving HTTP 200
       |                    |
       +---------+----------+
                 |
                 v
       Workload rescheduling
                 |
                 v
          2/2 replicas
                 |
                 v
        Remove network fault
                 |
                 v
          Agent-0 -> Ready
                 |
                 v
       Guardian -> NORMAL
