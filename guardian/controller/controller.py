import sys
from dataclasses import dataclass
from pathlib import Path
import sys
from pathlib import Path

GUARDIAN_DIR = Path(__file__).resolve().parent.parent

if str(GUARDIAN_DIR) not in sys.path:
    sys.path.insert(0, str(GUARDIAN_DIR))
    
from detector.evidence import collect_node_evidence
from detector.detector import classify_node


# ---------------------------------------------------------
# Make guardian/recovery modules importable
# ---------------------------------------------------------

CURRENT_DIR = Path(__file__).resolve().parent
GUARDIAN_DIR = CURRENT_DIR.parent

if str(GUARDIAN_DIR) not in sys.path:
    sys.path.insert(0, str(GUARDIAN_DIR))


from recovery.audit import AuditLogger
from recovery.executor import (
    ExecutionMode,
    RecoveryExecutor,
)
from recovery.policy import (
    RecoveryAction,
    decide_recovery,
)


@dataclass
class ControllerResult:
    node: str
    condition: str
    confidence: int
    workload_healthy: bool
    previous_attempts: int
    current_attempt: int
    decision: str
    execution_status: str
    message: str


class RecoveryController:

    def __init__(
        self,
        namespace: str,
        workload: str,
        max_recovery_attempts: int = 2,
        execution_mode: ExecutionMode = ExecutionMode.DRY_RUN,
        audit_file: Path | None = None,
    ):

        self.namespace = namespace
        self.workload = workload
        self.max_recovery_attempts = max_recovery_attempts

        self.executor = RecoveryExecutor(
            mode=execution_mode
        )

        if audit_file is None:
            self.logger = AuditLogger()
        else:
            self.logger = AuditLogger(
                audit_file=audit_file
            )

    def process(
        self,
        node: str,
        condition: str,
        confidence: int,
        workload_healthy: bool,
    ) -> ControllerResult:

        previous_attempts = (
            self.logger.get_attempt_count(node)
        )

        decision = decide_recovery(
            condition=condition,
            workload_healthy=workload_healthy,
            recovery_attempts=previous_attempts,
            max_recovery_attempts=self.max_recovery_attempts,
        )

        current_attempt = previous_attempts

        execution_status = "NOT_EXECUTED"
        message = decision.reason

        # -------------------------------------------------
        # NO ACTION
        # -------------------------------------------------

        if decision.action == RecoveryAction.NO_ACTION:

            return ControllerResult(
                node=node,
                condition=condition,
                confidence=confidence,
                workload_healthy=workload_healthy,
                previous_attempts=previous_attempts,
                current_attempt=current_attempt,
                decision=decision.action.value,
                execution_status=execution_status,
                message=message,
            )

        # -------------------------------------------------
        # MONITOR
        # -------------------------------------------------

        if decision.action == RecoveryAction.MONITOR:

            return ControllerResult(
                node=node,
                condition=condition,
                confidence=confidence,
                workload_healthy=workload_healthy,
                previous_attempts=previous_attempts,
                current_attempt=current_attempt,
                decision=decision.action.value,
                execution_status=execution_status,
                message=message,
            )

        # -------------------------------------------------
        # ESCALATE
        # -------------------------------------------------

        if decision.action == RecoveryAction.ESCALATE:

            return ControllerResult(
                node=node,
                condition=condition,
                confidence=confidence,
                workload_healthy=workload_healthy,
                previous_attempts=previous_attempts,
                current_attempt=current_attempt,
                decision=decision.action.value,
                execution_status=execution_status,
                message=message,
            )

        # -------------------------------------------------
        # RECOVER
        # -------------------------------------------------

        if decision.action == RecoveryAction.RECOVER:

            current_attempt = previous_attempts + 1

            execution = self.executor.recover_node(
                node
            )

            execution_status = (
                execution.status.value
            )

            message = execution.message

            # -------------------------------------------------
            # Record the recovery attempt.
            #
            # In DRY_RUN mode this records that the attempt
            # was evaluated but the command was intentionally
            # not executed.
            # -------------------------------------------------

            if execution_status == "EXECUTED":

                verification_status = "PENDING"
                final_state = "RECOVERY_PENDING"

            else:

                verification_status = "NOT_RUN"
                final_state = "DRY_RUN"

            self.logger.record(

                node=node,

                condition=condition,

                confidence=confidence,

                workload_healthy=workload_healthy,

                decision=decision.action.value,

                attempt=current_attempt,

                action=decision.action.value,

                execution_status=execution_status,

                verification_status=verification_status,

                final_state=final_state,

                message=message,
            )

            return ControllerResult(
                node=node,
                condition=condition,
                confidence=confidence,
                workload_healthy=workload_healthy,
                previous_attempts=previous_attempts,
                current_attempt=current_attempt,
                decision=decision.action.value,
                execution_status=execution_status,
                message=message,
            )

        # -------------------------------------------------
        # SAFETY FALLBACK
        # -------------------------------------------------

        return ControllerResult(
            node=node,
            condition=condition,
            confidence=confidence,
            workload_healthy=workload_healthy,
            previous_attempts=previous_attempts,
            current_attempt=current_attempt,
            decision="ESCALATE",
            execution_status="NOT_EXECUTED",
            message="Unknown controller state. Recovery blocked.",
        )


def print_result(result: ControllerResult):

    print(
        f"Node              : {result.node}"
    )

    print(
        f"Condition         : {result.condition}"
    )

    print(
        f"Confidence        : {result.confidence}%"
    )

    print(
        f"Workload Healthy  : {result.workload_healthy}"
    )

    print(
        f"Previous Attempts : {result.previous_attempts}"
    )

    print(
        f"Current Attempt   : {result.current_attempt}"
    )

    print(
        f"Decision           : {result.decision}"
    )

    print(
        f"Execution Status   : {result.execution_status}"
    )

    print(
        f"Message            : {result.message}"
    )

    print()




def main():

    from kubernetes import client, config
    import docker
    import yaml

    from detector.evidence import collect_node_evidence
    from detector.detector import (
        classify_node,
    )

    print("======================================")
    print(" CLOUD-138 RECOVERY CONTROLLER")
    print("======================================")
    print()

    # -----------------------------------------------------
    # Load configuration
    # -----------------------------------------------------

    config_file = GUARDIAN_DIR / "config.yaml"

    with open(
        config_file,
        "r",
        encoding="utf-8",
    ) as file:
        cfg = yaml.safe_load(file)

    namespace = cfg.get(
        "namespace",
        "edge-lab",
    )

    workload = cfg.get(
        "workload",
        "edge-workload",
    )

    print(f"Config            : {config_file}")
    print(f"Namespace         : {namespace}")
    print(f"Workload          : {workload}")
    print()

    # -----------------------------------------------------
    # Connect to Kubernetes and Docker
    # -----------------------------------------------------

    config.load_kube_config()

    core_api = client.CoreV1Api()
    apps_api = client.AppsV1Api()

    docker_client = docker.from_env()

    # -----------------------------------------------------
    # Read workload health
    # -----------------------------------------------------

    deployment = apps_api.read_namespaced_deployment(
        name=workload,
        namespace=namespace,
    )

    desired = deployment.spec.replicas or 0
    ready = deployment.status.ready_replicas or 0
    available = (
        deployment.status.available_replicas or 0
    )

    workload_healthy = (
        desired > 0
        and ready == desired
        and available == desired
    )

    # -----------------------------------------------------
    # Find nodes hosting workload
    # -----------------------------------------------------

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

    print(
        f"Workload Healthy  : "
        f"{workload_healthy}"
    )

    print(
        f"Replicas          : "
        f"{ready}/{desired}"
    )

    print(
        f"Available          : "
        f"{available}/{desired}"
    )

    print(
        "Workload nodes     : "
        f"{', '.join(sorted(workload_nodes)) or 'None'}"
    )

    print()

    # -----------------------------------------------------
    # Create controller
    #
    # IMPORTANT:
    # Keep DRY_RUN for this first real-cluster test.
    # -----------------------------------------------------

    controller = RecoveryController(
        namespace=namespace,
        workload=workload,
        max_recovery_attempts=2,
        execution_mode=ExecutionMode.DRY_RUN,
    )

    # -----------------------------------------------------
    # Collect and classify REAL nodes
    # -----------------------------------------------------

    nodes = core_api.list_node()

    for node in nodes.items:

        evidence = collect_node_evidence(
            core_api,
            docker_client,
            node,
        )

        detection = classify_node(
            node_name=evidence.node_name,
            node_ready=evidence.node_ready,
            docker_running=evidence.runtime_running,
            k3s_process_alive=evidence.k3s_process_alive,
            workload_on_node=(
                evidence.node_name
                in workload_nodes
            ),
            workload_healthy=workload_healthy,
        )

        # -------------------------------------------------
        # Send real detection result to controller
        # -------------------------------------------------

        result = controller.process(
            node=evidence.node_name,
            condition=detection.condition.value,
            confidence=detection.confidence,
            workload_healthy=workload_healthy,
        )

        print(
            f"Node              : "
            f"{result.node}"
        )

        print(
            f"Condition         : "
            f"{result.condition}"
        )

        print(
            f"Confidence        : "
            f"{result.confidence}%"
        )

        print(
            f"Workload Healthy  : "
            f"{result.workload_healthy}"
        )

        print(
            f"Previous Attempts : "
            f"{result.previous_attempts}"
        )

        print(
            f"Current Attempt   : "
            f"{result.current_attempt}"
        )

        print(
            f"Decision          : "
            f"{result.decision}"
        )

        print(
            f"Execution Status  : "
            f"{result.execution_status}"
        )

        print(
            f"Message           : "
            f"{result.message}"
        )

        print()

    print("--------------------------------------")
    print(" REAL CLUSTER SCAN COMPLETE")
    print("--------------------------------------")


if __name__ == "__main__":
    main()