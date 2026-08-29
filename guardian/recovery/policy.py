from dataclasses import dataclass
from enum import Enum


class RecoveryAction(Enum):
    NO_ACTION = "NO_ACTION"
    MONITOR = "MONITOR"
    RECOVER = "RECOVER"
    ESCALATE = "ESCALATE"


@dataclass
class RecoveryDecision:
    action: RecoveryAction
    reason: str
    confidence: int


def decide_recovery(
    condition: str,
    workload_healthy: bool,
    recovery_attempts: int = 0,
    max_recovery_attempts: int = 2,
) -> RecoveryDecision:

    condition = condition.upper()

    # Normal operation
    if condition == "READY":
        return RecoveryDecision(
            action=RecoveryAction.NO_ACTION,
            reason="Node is healthy. No recovery action is required.",
            confidence=100,
        )

    # Temporary control-plane connectivity problem
    if condition == "DISCONNECTED":
        return RecoveryDecision(
            action=RecoveryAction.MONITOR,
            reason=(
                "Node appears disconnected from the control plane. "
                "Do not restart the node; continue monitoring and "
                "wait for connectivity recovery."
            ),
            confidence=90,
        )

    # Actual node/runtime failure
    if condition == "FAILED":

        if recovery_attempts >= max_recovery_attempts:
            return RecoveryDecision(
                action=RecoveryAction.ESCALATE,
                reason=(
                    "Maximum recovery attempts have been reached. "
                    "Further automatic recovery is blocked."
                ),
                confidence=95,
            )

        if workload_healthy:
            return RecoveryDecision(
                action=RecoveryAction.RECOVER,
                reason=(
                    "Node failure detected while the workload remains "
                    "healthy on other replicas. A controlled recovery "
                    "attempt is permitted."
                ),
                confidence=95,
            )

        return RecoveryDecision(
            action=RecoveryAction.ESCALATE,
            reason=(
                "Node failure detected and workload health is degraded. "
                "Automatic recovery is blocked to prevent unsafe "
                "intervention."
            ),
            confidence=95,
        )

    # Unknown condition
    return RecoveryDecision(
        action=RecoveryAction.ESCALATE,
        reason=(
            "Failure condition is unknown. Insufficient evidence for "
            "automatic recovery."
        ),
        confidence=50,
    )


def main():

    print("======================================")
    print(" CLOUD-138 RECOVERY POLICY ENGINE")
    print("======================================")
    print()

    test_cases = [
        {
            "condition": "READY",
            "workload_healthy": True,
        },
        {
            "condition": "DISCONNECTED",
            "workload_healthy": True,
        },
        {
            "condition": "FAILED",
            "workload_healthy": True,
        },
        {
            "condition": "FAILED",
            "workload_healthy": False,
        },
        {
            "condition": "FAILED",
            "workload_healthy": True,
            "recovery_attempts": 2,
        },
        {
            "condition": "UNKNOWN",
            "workload_healthy": True,
        },
    ]

    for case in test_cases:

        decision = decide_recovery(**case)

        print(
            f"Condition={case['condition']} | "
            f"WorkloadHealthy={case['workload_healthy']}"
        )

        print(
            f"Action={decision.action.value} | "
            f"Confidence={decision.confidence}%"
        )

        print(
            f"Reason: {decision.reason}"
        )

        print()


if __name__ == "__main__":
    main()