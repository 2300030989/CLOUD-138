import time
from datetime import datetime

import yaml
from kubernetes import client, config
from kubernetes.client.rest import ApiException


CONFIG_FILE = "guardian/config.yaml"


def load_guardian_config():
    with open(CONFIG_FILE, "r") as file:
        config_data = yaml.safe_load(file)

    namespace = config_data["namespace"]
    workload = config_data["workload"]
    interval = int(config_data["check_interval"])

    return namespace, workload, interval


def load_kubernetes_config():
    config.load_kube_config()


def check_api(core_api):
    """
    Check authenticated Kubernetes API availability.
    """
    try:
        core_api.list_namespace(_request_timeout=3)
        return True

    except Exception:
        return False


def check_workload(apps_api, namespace, workload):
    """
    Check Deployment health.
    """
    try:
        deployment = apps_api.read_namespaced_deployment(
            name=workload,
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
    """
    Read Kubernetes node readiness.
    """
    try:
        nodes = core_api.list_node(_request_timeout=3)

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

    except Exception:
        return {}


def classify_state(api_healthy, workload_healthy, nodes):
    """
    Determine overall Guardian state.
    """

    if not api_healthy:
        return "DEGRADED"

    if not workload_healthy:
        return "WORKLOAD_FAILURE"

    if nodes and not all(nodes.values()):
        return "NODE_DEGRADED"

    return "NORMAL"


def main():

    namespace, workload, interval = load_guardian_config()

    print("======================================")
    print("      CLOUD-138 EDGE GUARDIAN")
    print("======================================")
    print()

    load_kubernetes_config()

    core_api = client.CoreV1Api()
    apps_api = client.AppsV1Api()

    print(f"Namespace : {namespace}")
    print(f"Workload  : {workload}")
    print(f"Interval  : {interval} seconds")
    print()
    print("Guardian started in READ-ONLY mode.")
    print()

    while True:

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        api_healthy = check_api(core_api)

        workload_healthy, desired, ready, available = check_workload(
            apps_api,
            namespace,
            workload,
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

            status = (
                "Ready"
                if node_ready
                else "NotReady"
            )

            print(
                f"    Node: {node_name} -> {status}"
            )

        print()

        time.sleep(interval)


if __name__ == "__main__":
    main()