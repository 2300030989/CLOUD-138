import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


BASE_DIR = Path(__file__).resolve().parent
AUDIT_FILE = BASE_DIR / "events.jsonl"


@dataclass
class RecoveryEvent:

    timestamp: str
    node: str
    condition: str
    confidence: int
    workload_healthy: bool
    decision: str
    attempt: int
    action: str
    execution_status: str
    verification_status: str
    final_state: str
    message: str


class AuditLogger:

    def __init__(
        self,
        audit_file: Path = AUDIT_FILE,
    ):
        self.audit_file = audit_file

        self.audit_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def get_attempt_count(self, node: str) -> int:
        if not self.audit_file.exists():
            return 0

        attempts = 0

        with self.audit_file.open(
            "r",
            encoding="utf-8",
        ) as file:

            for line in file:

                line = line.strip()

                if not line:
                    continue

                try:
                    event = json.loads(line)

                except json.JSONDecodeError:
                    continue

                if event.get("node") != node:
                    continue

                if event.get("action") == "RECOVER":
                    attempts = max(
                        attempts,
                        int(event.get("attempt", 0)),
                    )

        return attempts
    
   
    def record(
        self,
        node: str,
        condition: str,
        confidence: int,
        workload_healthy: bool,
        decision: str,
        attempt: int,
        action: str,
        execution_status: str,
        verification_status: str,
        final_state: str,
        message: str,
    ):

        event = RecoveryEvent(
            timestamp=datetime.now(
                timezone.utc
            ).isoformat(),

            node=node,

            condition=condition,

            confidence=confidence,

            workload_healthy=workload_healthy,

            decision=decision,

            attempt=attempt,

            action=action,

            execution_status=execution_status,

            verification_status=verification_status,

            final_state=final_state,

            message=message,
        )

        with self.audit_file.open(
            "a",
            encoding="utf-8",
        ) as file:

            json.dump(
                asdict(event),
                file,
                ensure_ascii=False,
            )

            file.write("\n")


def main():

    print("======================================")
    print(" CLOUD-138 AUDIT LOGGER")
    print("======================================")
    print()

    logger = AuditLogger()

    node = "k3d-cloud138-agent-0"

    previous_attempts = logger.get_attempt_count(node)
    current_attempt = previous_attempts + 1

    print(f"Node              : {node}")
    print(f"Previous attempts : {previous_attempts}")
    print(f"Current attempt   : {current_attempt}")
    print()

    logger.record(
        node=node,

        condition="FAILED",

        confidence=95,

        workload_healthy=True,

        decision="RECOVER",

        attempt=current_attempt,

        action="RECOVER",

        execution_status="EXECUTED",

        verification_status="RECOVERED",

        final_state="HEALTHY",

        message=(
            "Node failure recovered successfully."
        ),
    )

    print(
        "Audit event written to:"
    )

    print(
        logger.audit_file
    )

    print()

    print("Event recorded successfully.")


if __name__ == "__main__":
    main()