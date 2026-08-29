from dataclasses import dataclass
from enum import Enum

from kubernetes import client, config

from .evidence import collect_node_evidence


class NodeCondition(Enum):
    READY = "READY"
    DISCONNECTED = "DISCONNECTED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


@dataclass
class DetectionResult:
    node: str
    condition: NodeCondition
    confidence: int
    reason: str


def classify_node(
    node_name,
    node_ready,
    docker_running,
    k3s_process_alive,
    workload_on_node,
    workload_healthy,
):
    """
    Classify a node using multiple independent evidence signals.
    """

    # Healthy node
    if (
        node_ready
        and docker_running
        and k3s_process_alive
    ):
        return DetectionResult(
            node=node_name,
            condition=NodeCondition.READY,
            confidence=100,
            reason=(
                "Kubernetes reports the node Ready, "
                "the Docker runtime is running, and "
                "the K3s process is alive."
            ),
        )

    # Control-plane connectivity interruption
    if (
        not node_ready
        and docker_running
        and k3s_process_alive
        and workload_healthy
    ):
        return DetectionResult(
            node=node_name,
            condition=NodeCondition.DISCONNECTED,
            confidence=90,
            reason=(
                "The node is NotReady while its Docker runtime "
                "and K3s process remain alive and the cluster "
                "workload remains healthy. This is consistent "
                "with a control-plane connectivity interruption."
            ),
        )

    # Actual runtime/node failure
    if (
        not node_ready
        and not docker_running
        and not k3s_process_alive
    ):
        return DetectionResult(
            node=node_name,
            condition=NodeCondition.FAILED,
            confidence=95,
            reason=(
                "The node is NotReady and its underlying Docker "
                "runtime is stopped with no K3s process detected."
            ),
        )

    # Node NotReady but evidence is incomplete
    if not node_ready:
        return DetectionResult(
            node=node_name,
            condition=NodeCondition.UNKNOWN,
            confidence=50,
            reason=(
                "The node is NotReady, but the available evidence "
                "does not provide enough information to confidently "
                "classify the cause."
            ),
        )

    return DetectionResult(
        node=node_name,
        condition=NodeCondition.UNKNOWN,
        confidence=25,
        reason="Unexpected evidence combination.",
    )


def get_workload_nodes(core_api, namespace, workload_name):
    """
    Return the Kubernetes nodes currently hosting workload pods.
    """

    apps_api = client.AppsV1Api()

    deployment = apps_api.read_namespaced_deployment(
        name=workload_name,
        namespace=namespace,
    )

    selector = deployment.spec.selector.match_labels

    label_selector = ",".join(
        f"{key}={value}"
        for key, value in selector.items()
    )

    pods = core_api.list_namespaced_pod(
        namespace=namespace,
        label_selector=label_selector,
    )

    workload_nodes = set()

    for pod in pods.items:

        if pod.status.phase == "Running":
            if pod.spec.node_name:
                workload_nodes.add(pod.spec.node_name)

    return workload_nodes


def get_workload_health(apps_api, namespace, workload_name):
    """
    Read Deployment health.
    """

    deployment = apps_api.read_namespaced_deployment(
        name=workload_name,
        namespace=namespace,
    )

    desired = deployment.spec.replicas or 0
    ready = deployment.status.ready_replicas or 0
    available = deployment.status.available_replicas or 0

    healthy = (
        desired > 0
        and ready == desired
        and available == desired
    )

    return healthy, desired, ready, available


def main():

    namespace = "edge-lab"
    workload_name = "edge-workload"

    print("======================================")
    print(" CLOUD-138 NODE FAILURE DETECTOR v3")
    print("======================================")
    print()

    config.load_kube_config()

    core_api = client.CoreV1Api()
    apps_api = client.AppsV1Api()

    docker_client = __import__("docker").from_env()

    workload_healthy, desired, ready, available = (
        get_workload_health(
            apps_api,
            namespace,
            workload_name,
        )
    )

    workload_nodes = get_workload_nodes(
        core_api,
        namespace,
        workload_name,
    )

    print(
        f"Workload : {workload_name}"
    )

    print(
        f"Replicas : {ready}/{desired}"
    )

    print(
        f"Available: {available}"
    )

    print(
        f"Healthy  : {workload_healthy}"
    )

    print(
        f"Nodes hosting workload: "
        f"{', '.join(sorted(workload_nodes)) or 'None'}"
    )

    print()

    nodes = core_api.list_node()

    for node in nodes.items:

        evidence = collect_node_evidence(
            core_api,
            docker_client,
            node,
        )

        result = classify_node(
            node_name=evidence.node_name,
            node_ready=evidence.node_ready,
            docker_running=evidence.runtime_running,
            k3s_process_alive=evidence.k3s_process_alive,
            workload_on_node=(
                evidence.node_name in workload_nodes
            ),
            workload_healthy=workload_healthy,
        )

        print(
            f"Node={result.node} | "
            f"CONDITION={result.condition.value} | "
            f"CONFIDENCE={result.confidence}%"
        )

        print(
            f"  Kubernetes Ready : "
            f"{evidence.node_ready}"
        )

        print(
            f"  Docker Runtime    : "
            f"{evidence.runtime_status}"
        )

        print(
            f"  K3s Process       : "
            f"{evidence.k3s_process_alive}"
        )

        print(
            f"  Workload on node  : "
            f"{evidence.node_name in workload_nodes}"
        )

        print(
            f"  Reason            : "
            f"{result.reason}"
        )

        print()


if __name__ == "__main__":
    main()