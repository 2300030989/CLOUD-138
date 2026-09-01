import sys
import time
from dataclasses import dataclass
from pathlib import Path

import yaml


# ---------------------------------------------------------
# Make guardian/ modules importable
# ---------------------------------------------------------

CURRENT_DIR = Path(__file__).resolve().parent
GUARDIAN_DIR = CURRENT_DIR.parent

if str(GUARDIAN_DIR) not in sys.path:
    sys.path.insert(0, str(GUARDIAN_DIR))


from detector.evidence import collect_node_evidence
from detector.detector import classify_node

from recovery.audit import AuditLogger

from recovery.executor import (
    ExecutionMode,
    ExecutionStatus,
    RecoveryExecutor,
)

from recovery.policy import (
    RecoveryAction,
    decide_recovery,
)

from recovery.verify import verify_recovery


# ---------------------------------------------------------
# Controller result
# ---------------------------------------------------------

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

    verification_status: str

    final_state: str

    message: str


# ---------------------------------------------------------
# Recovery Controller
# ---------------------------------------------------------

class RecoveryController:

    def __init__(
        self,
        namespace: str,
        workload: str,
        max_recovery_attempts: int = 2,
        execution_mode: ExecutionMode = ExecutionMode.DRY_RUN,
        live_recovery_enabled: bool = False,
        recovery_session: str = "default",
        audit_file: Path | None = None,
        wait_after_execution: int = 10,
        verification_timeout: int = 60,
    ):

        self.namespace = namespace

        self.workload = workload

        self.max_recovery_attempts = (
            max_recovery_attempts
        )

        self.wait_after_execution = (
            wait_after_execution
        )

        self.verification_timeout = (
            verification_timeout
        )

        self.execution_mode = execution_mode

        self.live_recovery_enabled = (
            live_recovery_enabled
        )

        self.recovery_session = (
            recovery_session
        )

        self.executor = RecoveryExecutor(
            mode=execution_mode
        )

        if audit_file is None:

            self.logger = AuditLogger(
                session=self.recovery_session
            )

        else:

            self.logger = AuditLogger(
                audit_file=audit_file,
                session=self.recovery_session,
            )


    # -----------------------------------------------------
    # Authorization
    # -----------------------------------------------------

    def live_recovery_authorized(self) -> bool:

        return (
            self.execution_mode
            == ExecutionMode.LIVE
            and self.live_recovery_enabled
        )


    # -----------------------------------------------------
    # Verification helper
    # -----------------------------------------------------

    def verify_after_recovery(
        self,
        node: str,
    ):

        deadline = (
            time.monotonic()
            + self.verification_timeout
        )

        last_result = None

        while time.monotonic() < deadline:

            remaining = (
                deadline
                - time.monotonic()
            )

            if remaining <= 0:
                break

            result = verify_recovery(
                node_name=node,
                namespace=self.namespace,
                workload_name=self.workload,
                wait_seconds=0,
            )

            last_result = result

            if result.recovered:

                return result

            time.sleep(
                min(2, max(0, remaining))
            )

        return last_result


    # -----------------------------------------------------
    # Process one node
    # -----------------------------------------------------

    def process(
        self,
        node: str,
        condition: str,
        confidence: int,
        workload_healthy: bool,
    ) -> ControllerResult:

        previous_attempts = (
            self.logger.get_attempt_count(
                node
            )
        )

        decision = decide_recovery(
            condition=condition,
            workload_healthy=workload_healthy,
            recovery_attempts=previous_attempts,
            max_recovery_attempts=self.max_recovery_attempts,
        )

        current_attempt = previous_attempts

        execution_status = (
            ExecutionStatus.SKIPPED.value
            if decision.action == RecoveryAction.RECOVER
            else "NOT_EXECUTED"
        )

        verification_status = "NOT_RUN"

        final_state = "NO_ACTION"

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
                execution_status="NOT_EXECUTED",
                verification_status="NOT_RUN",
                final_state="HEALTHY",
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
                execution_status="NOT_EXECUTED",
                verification_status="NOT_RUN",
                final_state="MONITORING",
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
                execution_status="NOT_EXECUTED",
                verification_status="NOT_RUN",
                final_state="ESCALATED",
                message=message,
            )


        # -------------------------------------------------
        # RECOVER
        # -------------------------------------------------

        if decision.action == RecoveryAction.RECOVER:

            current_attempt = (
                previous_attempts + 1
            )


            # -------------------------------------------------
            # LIVE AUTHORIZATION GATE
            # -------------------------------------------------

            if (
                self.execution_mode
                == ExecutionMode.LIVE
                and not self.live_recovery_enabled
            ):

                execution_status = "BLOCKED"

                verification_status = "NOT_RUN"

                final_state = "AUTHORIZATION_BLOCKED"

                message = (
                    "LIVE execution was requested, "
                    "but live_recovery_enabled is false. "
                    "Automatic recovery is blocked."
                )

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
                    verification_status=verification_status,
                    final_state=final_state,
                    message=message,
                )


            execution = self.executor.recover_node(
                node
            )

            execution_status = (
                execution.status.value
            )

            message = execution.message


            # -------------------------------------------------
            # DRY RUN
            # -------------------------------------------------

            if (
                execution.status
                == ExecutionStatus.SKIPPED
            ):

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
                    verification_status=verification_status,
                    final_state=final_state,
                    message=message,
                )


            # -------------------------------------------------
            # EXECUTION FAILED
            # -------------------------------------------------

            if (
                execution.status
                == ExecutionStatus.FAILED
            ):

                verification_status = "NOT_RUN"

                final_state = "EXECUTION_FAILED"

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
                    verification_status=verification_status,
                    final_state=final_state,
                    message=message,
                )


            # -------------------------------------------------
            # LIVE EXECUTION SUCCESS
            # -------------------------------------------------

            if (
                execution.status
                == ExecutionStatus.EXECUTED
            ):

                verification_status = "PENDING"

                final_state = "RECOVERY_PENDING"

                if self.wait_after_execution > 0:

                    time.sleep(
                        self.wait_after_execution
                    )


                verification = (
                    self.verify_after_recovery(
                        node
                    )
                )


                if (
                    verification is not None
                    and verification.recovered
                ):

                    verification_status = (
                        "RECOVERED"
                    )

                    final_state = "HEALTHY"

                    message = (
                        "Recovery executed successfully "
                        "and verification confirmed that "
                        "the node and workload are healthy. "
                        + verification.reason
                    )

                else:

                    verification_status = (
                        "RECOVERY_FAILED"
                    )

                    final_state = (
                        "RECOVERY_FAILED"
                    )

                    if verification is None:

                        message = (
                            "Recovery command executed, "
                            "but verification produced "
                            "no result before the timeout."
                        )

                    else:

                        message = (
                            "Recovery command executed, "
                            "but post-recovery verification "
                            "failed. "
                            + verification.reason
                        )


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
                    verification_status=verification_status,
                    final_state=final_state,
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
            verification_status="NOT_RUN",
            final_state="ESCALATED",
            message="Unknown controller state. Recovery blocked.",
        )


# ---------------------------------------------------------
# Output
# ---------------------------------------------------------

def print_result(
    result: ControllerResult,
):

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
        f"Verification      : "
        f"{result.verification_status}"
    )

    print(
        f"Final State       : "
        f"{result.final_state}"
    )

    print(
        f"Message           : "
        f"{result.message}"
    )

    print()


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main():

    from kubernetes import client, config
    import docker


    print(
        "======================================"
    )

    print(
        " CLOUD-138 RECOVERY CONTROLLER"
    )

    print(
        "======================================"
    )

    print()


    # -----------------------------------------------------
    # Load configuration
    # -----------------------------------------------------

    config_file = (
        GUARDIAN_DIR
        / "config.yaml"
    )

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


    max_recovery_attempts = int(
        cfg.get(
            "max_recovery_attempts",
            2,
        )
    )


    execution_mode_name = str(
        cfg.get(
            "execution_mode",
            "DRY_RUN",
        )
    ).upper()


    try:

        execution_mode = (
            ExecutionMode[
                execution_mode_name
            ]
        )

    except KeyError:

        raise ValueError(
            f"Invalid execution_mode: "
            f"{execution_mode_name}. "
            f"Expected one of: "
            f"{', '.join(mode.name for mode in ExecutionMode)}"
        )


    live_recovery_enabled = bool(
        cfg.get(
            "live_recovery_enabled",
            False,
        )
    )


    recovery_session = str(
        cfg.get(
            "recovery_session",
            "default",
        )
    )


    recovery_config = cfg.get(
        "recovery",
        {},
    )


    wait_after_execution = int(
        recovery_config.get(
            "wait_after_execution",
            10,
        )
    )


    verification_timeout = int(
        recovery_config.get(
            "verification_timeout",
            60,
        )
    )


    print(
        f"Config            : "
        f"{config_file}"
    )

    print(
        f"Namespace         : "
        f"{namespace}"
    )

    print(
        f"Workload          : "
        f"{workload}"
    )

    print(
        f"Execution Mode    : "
        f"{execution_mode.value}"
    )

    print(
        f"Live Recovery     : "
        f"{live_recovery_enabled}"
    )

    print(
        f"Recovery Session  : "
        f"{recovery_session}"
    )

    print(
        f"Max Recovery Attempts : "
        f"{max_recovery_attempts}"
    )

    print(
        f"Wait After Execution : "
        f"{wait_after_execution}s"
    )

    print(
        f"Verification Timeout : "
        f"{verification_timeout}s"
    )

    print()


    # -----------------------------------------------------
    # Authorization summary
    # -----------------------------------------------------

    if execution_mode == ExecutionMode.LIVE:

        if live_recovery_enabled:

            print(
                "LIVE RECOVERY AUTHORIZATION : ENABLED"
            )

            print(
                "Automatic recovery actions are permitted."
            )

        else:

            print(
                "LIVE RECOVERY AUTHORIZATION : BLOCKED"
            )

            print(
                "execution_mode=LIVE but "
                "live_recovery_enabled=false."
            )

    else:

        print(
            "LIVE RECOVERY AUTHORIZATION : "
            "NOT REQUESTED"
        )

        print(
            "Controller is operating in DRY_RUN mode."
        )

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

    deployment = (
        apps_api.read_namespaced_deployment(
            name=workload,
            namespace=namespace,
        )
    )


    desired = (
        deployment.spec.replicas
        or 0
    )

    ready = (
        deployment.status.ready_replicas
        or 0
    )

    available = (
        deployment.status.available_replicas
        or 0
    )


    workload_healthy = (
        desired > 0
        and ready == desired
        and available == desired
    )


    # -----------------------------------------------------
    # Find nodes hosting workload
    # -----------------------------------------------------

    selector = (
        deployment.spec.selector.match_labels
    )


    label_selector = ",".join(
        f"{key}={value}"
        for key, value
        in selector.items()
    )


    pods = (
        core_api.list_namespaced_pod(
            namespace=namespace,
            label_selector=label_selector,
        )
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
        + (
            ", ".join(
                sorted(workload_nodes)
            )
            or "None"
        )
    )

    print()


    # -----------------------------------------------------
    # Create controller
    # -----------------------------------------------------

    controller = RecoveryController(

        namespace=namespace,

        workload=workload,

        max_recovery_attempts=(
            max_recovery_attempts
        ),

        execution_mode=(
            execution_mode
        ),

        live_recovery_enabled=(
            live_recovery_enabled
        ),

        recovery_session=(
            recovery_session
        ),

        wait_after_execution=(
            wait_after_execution
        ),

        verification_timeout=(
            verification_timeout
        ),
    )


    # -----------------------------------------------------
    # Collect and classify REAL nodes
    # -----------------------------------------------------

    nodes = core_api.list_node()


    for node in nodes.items:

        evidence = (
            collect_node_evidence(
                core_api,
                docker_client,
                node,
            )
        )


        detection = (
            classify_node(

                node_name=(
                    evidence.node_name
                ),

                node_ready=(
                    evidence.node_ready
                ),

                docker_running=(
                    evidence.runtime_running
                ),

                k3s_process_alive=(
                    evidence.k3s_process_alive
                ),

                workload_on_node=(
                    evidence.node_name
                    in workload_nodes
                ),

                workload_healthy=(
                    workload_healthy
                ),
            )
        )


        # -------------------------------------------------
        # Send detection result to controller
        # -------------------------------------------------

        result = controller.process(

            node=(
                evidence.node_name
            ),

            condition=(
                detection.condition.value
            ),

            confidence=(
                detection.confidence
            ),

            workload_healthy=(
                workload_healthy
            ),
        )


        print_result(
            result
        )


    print(
        "--------------------------------------"
    )

    print(
        " REAL CLUSTER SCAN COMPLETE"
    )

    print(
        "--------------------------------------"
    )


# ---------------------------------------------------------
# Entry point
# ---------------------------------------------------------

if __name__ == "__main__":

    main()