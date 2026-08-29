from dataclasses import dataclass
from typing import Optional

import docker


@dataclass
class NodeEvidence:
    node_name: str
    node_ready: bool
    node_ip: Optional[str]
    runtime_status: str
    runtime_running: bool
    k3s_process_alive: bool
    ready_message: str


def get_node_ready_status(node):
    """
    Read the Kubernetes Ready condition.
    """
    for condition in node.status.conditions or []:
        if condition.type == "Ready":
            if condition.status == "True":
                return True, "Node is Ready."

            return False, (
                f"Node is NotReady. "
                f"Reason={condition.reason}, "
                f"Message={condition.message}"
            )

    return False, "Node has no Ready condition."


def get_node_ip(node):
    """
    Get Kubernetes InternalIP.
    """
    for address in node.status.addresses or []:
        if address.type == "InternalIP":
            return address.address

    return None


def get_docker_container_name(node_name):
    """
    Convert Kubernetes k3d node name into Docker container name.
    """
    return node_name


def check_docker_runtime(docker_client, node_name):
    """
    Check whether the corresponding k3d Docker container is running.
    """
    container_name = get_docker_container_name(node_name)

    try:
        container = docker_client.containers.get(container_name)

        status = container.status

        return (
            status,
            status == "running",
        )

    except docker.errors.NotFound:
        return "not_found", False

    except Exception as exc:
        return f"error: {exc}", False


def check_k3s_process(docker_client, node_name):
    """
    Check whether a k3s process exists inside the node container.
    """
    try:
        container = docker_client.containers.get(node_name)

        result = container.exec_run(
            "sh -c \"ps | grep '[k]3s'\""
        )

        output = result.output.decode(
            "utf-8",
            errors="replace",
        ).strip()

        return bool(output)

    except Exception:
        return False


def collect_node_evidence(
    core_api,
    docker_client,
    node,
):
    """
    Collect all available evidence for one Kubernetes node.
    """
    node_name = node.metadata.name

    ready, ready_message = get_node_ready_status(node)

    node_ip = get_node_ip(node)

    runtime_status, runtime_running = check_docker_runtime(
        docker_client,
        node_name,
    )

    k3s_process_alive = check_k3s_process(
        docker_client,
        node_name,
    )

    return NodeEvidence(
        node_name=node_name,
        node_ready=ready,
        node_ip=node_ip,
        runtime_status=runtime_status,
        runtime_running=runtime_running,
        k3s_process_alive=k3s_process_alive,
        ready_message=ready_message,
    )


def main():

    from kubernetes import client, config

    config.load_kube_config()

    core_api = client.CoreV1Api()

    docker_client = docker.from_env()

    print("======================================")
    print(" CLOUD-138 NODE EVIDENCE COLLECTOR")
    print("======================================")
    print()

    nodes = core_api.list_node()

    for node in nodes.items:

        evidence = collect_node_evidence(
            core_api,
            docker_client,
            node,
        )

        print(f"Node               : {evidence.node_name}")
        print(f"Ready              : {evidence.node_ready}")
        print(f"Ready evidence     : {evidence.ready_message}")
        print(f"Internal IP        : {evidence.node_ip}")
        print(f"Docker status      : {evidence.runtime_status}")
        print(f"Docker running     : {evidence.runtime_running}")
        print(f"K3s process alive  : {evidence.k3s_process_alive}")
        print()


if __name__ == "__main__":
    main()