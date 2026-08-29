from dataclasses import dataclass
from enum import Enum
import subprocess


class ExecutionMode(Enum):
    DRY_RUN = "DRY_RUN"
    LIVE = "LIVE"


class ExecutionStatus(Enum):
    SKIPPED = "SKIPPED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"


@dataclass
class RecoveryExecution:
    status: ExecutionStatus
    action: str
    target: str
    message: str


class RecoveryExecutor:

    def __init__(
        self,
        mode: ExecutionMode = ExecutionMode.DRY_RUN,
    ):
        self.mode = mode

    def recover_node(
        self,
        node_name: str,
    ) -> RecoveryExecution:

        if not node_name:
            return RecoveryExecution(
                status=ExecutionStatus.FAILED,
                action="RECOVER",
                target="UNKNOWN",
                message="Node name was not provided.",
            )

        command = [
            "docker",
            "start",
            node_name,
        ]

        if self.mode == ExecutionMode.DRY_RUN:

            return RecoveryExecution(
                status=ExecutionStatus.SKIPPED,
                action="RECOVER",
                target=node_name,
                message=(
                    "DRY_RUN enabled. Recovery command was not executed: "
                    + " ".join(command)
                ),
            )

        try:

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            if result.returncode == 0:

                return RecoveryExecution(
                    status=ExecutionStatus.EXECUTED,
                    action="RECOVER",
                    target=node_name,
                    message=(
                        "Recovery command executed successfully. "
                        f"Output: {result.stdout.strip()}"
                    ),
                )

            return RecoveryExecution(
                status=ExecutionStatus.FAILED,
                action="RECOVER",
                target=node_name,
                message=(
                    "Recovery command failed. "
                    f"ExitCode={result.returncode} "
                    f"Error={result.stderr.strip()}"
                ),
            )

        except Exception as exc:

            return RecoveryExecution(
                status=ExecutionStatus.FAILED,
                action="RECOVER",
                target=node_name,
                message=f"Recovery execution error: {exc}",
            )


def main():

    print("======================================")
    print(" CLOUD-138 RECOVERY EXECUTOR")
    print("======================================")
    print()

    executor = RecoveryExecutor(
        mode=ExecutionMode.DRY_RUN
    )

    test_nodes = [
        "k3d-cloud138-agent-0",
        "k3d-cloud138-agent-1",
    ]

    for node in test_nodes:

        result = executor.recover_node(node)

        print(
            f"Node   : {result.target}"
        )

        print(
            f"Action : {result.action}"
        )

        print(
            f"Status : {result.status.value}"
        )

        print(
            f"Message: {result.message}"
        )

        print()


if __name__ == "__main__":
    main()