import time
from datetime import datetime
from pathlib import Path

import yaml
from kubernetes import client, config
from kubernetes.client.rest import ApiException


BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.yaml"


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    namespace = cfg.get("namespace", "edge-lab")
    workload = cfg.get("workload", "edge-workload")
    interval = int(cfg.get("check_interval", 5))

    return namespace, workload, interval


def load_kubernetes_config():
    config.load_kube_config()


def check_api(core_api):
    try:
        core_api.list_namespace(_request_timeout=3)
        return True, "API reachable"

    except Exception as e:
        return False, str(e)


def check_workload(apps_api, namespace, workload_name):
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


def check_nodes(core_api):
    try:
        nodes = core_api.list_node()

        states = {}

        for node in nodes.items:
            name = node.metadata.name
            ready = False

            for condition in node.status.conditions or []:
                if condition.type == "Ready":
                    ready = condition.status == "True"
                    break

            states[name] = ready

        return states

    except ApiException:
        return {}


def classify_state(api_healthy, workload_healthy, nodes):

    not_ready_nodes = [
        name for name, ready in nodes.items()
        if not ready
    ]

    if api_healthy and workload_healthy and not not_ready_nodes:
        return "NORMAL"

    if not api_healthy and workload_healthy:
        return "DEGRADED"

    if api_healthy and workload_healthy and not_ready_nodes:
        return "NODE_DEGRADED"

    if not workload_healthy:
        return "WORKLOAD_FAILURE"

    return "UNKNOWN"


def main():

    namespace, workload_name, check_interval = load_config()

    print("======================================")
    print("      CLOUD-138 EDGE GUARDIAN")
    print("======================================")
    print()

    load_kubernetes_config()

    core_api = client.CoreV1Api()
    apps_api = client.AppsV1Api()

    print(f"Config    : {CONFIG_FILE}")
    print(f"Namespace : {namespace}")
    print(f"Workload  : {workload_name}")
    print(f"Interval  : {check_interval} seconds")
    print()
    print("Guardian started in READ-ONLY mode.")
    print()

    while True:

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        api_healthy, api_message = check_api(core_api)

        workload_healthy, desired, ready, available = check_workload(
            apps_api,
            namespace,
            workload_name,
        )

        nodes = check_nodes(core_api)

        state = classify_state(
            api_healthy,
            workload_healthy,
            nodes,
        )

        api_status = "HEALTHY" if api_healthy else "UNREACHABLE"

        workload_status = (
            "HEALTHY"
            if workload_healthy
            else "UNHEALTHY"
        )

        print(
            f"[{timestamp}] "
            f"API={api_status} | "
            f"WORKLOAD={workload_status} "
            f"({ready}/{desired}) | "
            f"STATE={state}"
        )

        for node_name, node_ready in nodes.items():

            status = "Ready" if node_ready else "NotReady"

            print(
                f"    Node: {node_name} -> {status}"
            )

        print()

        time.sleep(check_interval)


if __name__ == "__main__":
    main()
