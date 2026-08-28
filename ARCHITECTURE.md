# CLOUD-138 Architecture

## System Architecture

```text
                         CLOUD-138
                    Edge Resilience System
                             |
             +---------------+---------------+
             |                               |
             v                               v
      Kubernetes Cluster              Edge Guardian
             |                               |
     +-------+-------+                 +-----+------+
     |       |       |                 |            |
     v       v       v                 v            v
  Server   Agent-0  Agent-1       API Monitor   Node Monitor
    -0        |        |                 |
     |        |        |                 v
     |        |        |            Workload Monitor
     |        |        |
     |        +--------+-------------------+
     |                  |
     |             Edge Workload
     |             2 replicas
     |                  |
     |             +----+----+
     |             |         |
     |             v         v
     |          Replica-1  Replica-2
     |             |         |
     +-------------+---------+
                   |
                   v
            ClusterIP Service
                   |
                   v
          connectivity-test