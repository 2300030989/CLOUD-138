import sys
import time
from datetime import datetime
from pathlib import Path

import docker
import yaml
from kubernetes import client, config
from kubernetes.client.rest import ApiException


BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.yaml"

DETECTOR_DIR = BASE_DIR / "detector"

if str(DETECTOR_DIR) not in sys.path:
    sys.path.insert(0, str(DETECTOR_DIR))

from detector import classify_node
from evidence import collect_node_evidence


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    namespace = cfg.get("namespace", "edge-lab")
    workload = cfg.get("workload", "edge-workload")
    interval = int(cfg.get("check_interval", 5))

    return namespace, workload, interval


def load_kubernetes_config():
    config.load_kube_config()


def check_api(core_api):
    try:
        core_api.list_namespace(
            _request_timeout=3
        )

        return True, "API reachable"

    except Exception as exc:
        return False, str(exc)


def check_workload(
    apps_api,
    namespace,
    workload_name,
):
    try:
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

    except ApiException:
        return False, 0, 0, 0


def get_workload_nodes(
    core_api,
    namespace,
    workload_name,
):
    """
    Identify the Kubernetes nodes currently hosting
    running replicas of the configured workload.
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
                workload_nodes.add(
                    pod.spec.node_name
                )

    return workload_nodes


def main():

    namespace, workload_name, check_interval = load_config()

    print("======================================")
    print("      CLOUD-138 EDGE GUARDIAN v4")
    print("======================================")
    print()

    load_kubernetes_config()

    core_api = client.CoreV1Api()
    apps_api = client.AppsV1Api()

    docker_client = docker.from_env()

    print(f"Config    : {CONFIG_FILE}")
    print(f"Namespace : {namespace}")
    print(f"Workload  : {workload_name}")
    print(f"Interval  : {check_interval} seconds")
    print()
    print(
        "Guardian started in READ-ONLY mode."
    )
    print()

    while True:

        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # -------------------------------------------------
        # Kubernetes API
        # -------------------------------------------------

        api_healthy, api_message = check_api(
            core_api
        )

        # -------------------------------------------------
        # Workload
        # -------------------------------------------------

        (
            workload_healthy,
            desired,
            ready,
            available,
        ) = check_workload(
            apps_api,
            namespace,
            workload_name,
        )

        # -------------------------------------------------
        # Workload placement
        # -------------------------------------------------

        try:
            workload_nodes = get_workload_nodes(
                core_api,
                namespace,
                workload_name,
            )

        except Exception:
            workload_nodes = set()

        # -------------------------------------------------
        # Overall status
        # -------------------------------------------------

        api_status = (
            "HEALTHY"
            if api_healthy
            else "UNREACHABLE"
        )

        workload_status = (
            "HEALTHY"
            if workload_healthy
            else "UNHEALTHY"
        )

        print(
            f"[{timestamp}] "
            f"API={api_status} | "
            f"WORKLOAD={workload_status} "
            f"({ready}/{desired})"
        )

        print(
            f"    Available replicas: "
            f"{available}/{desired}"
        )

        print(
            "    Workload nodes: "
            f"{', '.join(sorted(workload_nodes)) or 'None'}"
        )

        # -------------------------------------------------
        # Real node evidence + classification
        # -------------------------------------------------

        try:
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
                    k3s_process_alive=(
                        evidence.k3s_process_alive
                    ),
                    workload_on_node=(
                        evidence.node_name
                        in workload_nodes
                    ),
                    workload_healthy=workload_healthy,
                )

                print(
                    f"    Node: {result.node}"
                )

                print(
                    f"        CONDITION="
                    f"{result.condition.value} "
                    f"| CONFIDENCE="
                    f"{result.confidence}%"
                )

                print(
                    f"        K8s Ready      : "
                    f"{evidence.node_ready}"
                )

                print(
                    f"        Docker Runtime: "
                    f"{evidence.runtime_status}"
                )

                print(
                    f"        K3s Process   : "
                    f"{evidence.k3s_process_alive}"
                )

                print(
                    f"        Workload      : "
                    f"{evidence.node_name in workload_nodes}"
                )

                print(
                    f"        Reason        : "
                    f"{result.reason}"
                )

        except Exception as exc:

            print(
                f"    NODE_EVIDENCE_ERROR: {exc}"
            )

        print()

        time.sleep(check_interval)


if __name__ == "__main__":
    main()