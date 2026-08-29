from dataclasses import dataclass
from typing import Optional
import subprocess
import time

from kubernetes import client, config
from kubernetes.client.rest import ApiException


@dataclass
class VerificationResult:
    node_name: str
    docker_running: bool
    k3s_alive: bool
    kubernetes_ready: bool
    workload_healthy: bool
    recovered: bool
    reason: str


def check_docker_running(node_name: str) -> bool:
    try:
        result = subprocess.run(
            [
                "docker",
                "inspect",
                "-f",
                "{{.State.Running}}",
                node_name,
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        return result.returncode == 0 and result.stdout.strip() == "true"

    except Exception:
        return False


def check_k3s_process(node_name: str) -> bool:
    try:
        result = subprocess.run(
            [
                "docker",
                "exec",
                node_name,
                "sh",
                "-c",
                "ps | grep '[k]3s'",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        return result.returncode == 0 and bool(result.stdout.strip())

    except Exception:
        return False


def check_kubernetes_ready(
    core_api: client.CoreV1Api,
    node_name: str,
) -> bool:

    try:
        node = core_api.read_node(node_name)

        for condition in node.status.conditions or []:

            if condition.type == "Ready":
                return condition.status == "True"

        return False

    except ApiException:
        return False


def check_workload_health(
    apps_api: client.AppsV1Api,
    namespace: str,
    workload_name: str,
) -> bool:

    try:
        deployment = apps_api.read_namespaced_deployment(
            name=workload_name,
            namespace=namespace,
        )

        desired = deployment.spec.replicas or 0
        ready = deployment.status.ready_replicas or 0
        available = deployment.status.available_replicas or 0

        return (
            desired > 0
            and ready == desired
            and available == desired
        )

    except ApiException:
        return False


def verify_recovery(
    node_name: str,
    namespace: str,
    workload_name: str,
    wait_seconds: int = 5,
) -> VerificationResult:

    time.sleep(wait_seconds)

    docker_running = check_docker_running(
        node_name
    )

    k3s_alive = check_k3s_process(
        node_name
    )

    try:
        config.load_kube_config()

        core_api = client.CoreV1Api()
        apps_api = client.AppsV1Api()

        kubernetes_ready = check_kubernetes_ready(
            core_api,
            node_name,
        )

        workload_healthy = check_workload_health(
            apps_api,
            namespace,
            workload_name,
        )

    except Exception:
        kubernetes_ready = False
        workload_healthy = False

    recovered = (
        docker_running
        and k3s_alive
        and kubernetes_ready
        and workload_healthy
    )

    if recovered:

        reason = (
            "Recovery verified successfully: Docker runtime is running, "
            "K3s process is alive, Kubernetes reports the node Ready, "
            "and the workload is healthy."
        )

    else:

        failed_checks = []

        if not docker_running:
            failed_checks.append("Docker runtime")

        if not k3s_alive:
            failed_checks.append("K3s process")

        if not kubernetes_ready:
            failed_checks.append("Kubernetes Ready")

        if not workload_healthy:
            failed_checks.append("workload health")

        reason = (
            "Recovery verification failed. "
            "Unhealthy checks: "
            + ", ".join(failed_checks)
        )

    return VerificationResult(
        node_name=node_name,
        docker_running=docker_running,
        k3s_alive=k3s_alive,
        kubernetes_ready=kubernetes_ready,
        workload_healthy=workload_healthy,
        recovered=recovered,
        reason=reason,
    )


def main():

    print("======================================")
    print(" CLOUD-138 RECOVERY VERIFIER")
    print("======================================")
    print()

    node_name = "k3d-cloud138-agent-0"
    namespace = "edge-lab"
    workload = "edge-workload"

    print(f"Node     : {node_name}")
    print(f"Namespace: {namespace}")
    print(f"Workload : {workload}")
    print()

    print("Verification started...")
    print()

    result = verify_recovery(
        node_name=node_name,
        namespace=namespace,
        workload_name=workload,
        wait_seconds=2,
    )

    print(
        f"Docker Runtime : {result.docker_running}"
    )

    print(
        f"K3s Process    : {result.k3s_alive}"
    )

    print(
        f"Kubernetes Ready: {result.kubernetes_ready}"
    )

    print(
        f"Workload Healthy: {result.workload_healthy}"
    )

    print()

    status = (
        "RECOVERED"
        if result.recovered
        else "RECOVERY_FAILED"
    )

    print(
        f"RESULT         : {status}"
    )

    print(
        f"Reason         : {result.reason}"
    )


if __name__ == "__main__":
    main()