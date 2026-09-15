import json
from collections import Counter
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
AUDIT_FILE = BASE_DIR / "events.jsonl"
REPORT_FILE = BASE_DIR / "audit-report.txt"

TARGET_SESSION = "O5-live-recovery"


def format_timestamp(timestamp: str) -> str:
    try:
        value = datetime.fromisoformat(
            timestamp.replace("Z", "+00:00")
        )

        return value.strftime(
            "%d-%b-%Y %H:%M:%S UTC"
        )

    except (ValueError, TypeError):
        return timestamp


def yes_no(value: bool) -> str:
    return "YES" if value else "NO"


def load_events():
    if not AUDIT_FILE.exists():
        return []

    events = []

    with AUDIT_FILE.open(
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

            if event.get("session") == TARGET_SESSION:
                events.append(event)

    return events


def build_event_section(
    event: dict,
    event_number: int,
) -> str:

    timestamp = format_timestamp(
        event.get("timestamp", "UNKNOWN")
    )

    node = event.get(
        "node",
        "UNKNOWN",
    )

    condition = event.get(
        "condition",
        "UNKNOWN",
    )

    confidence = event.get(
        "confidence",
        0,
    )

    workload_healthy = event.get(
        "workload_healthy",
        False,
    )

    decision = event.get(
        "decision",
        "UNKNOWN",
    )

    attempt = event.get(
        "attempt",
        0,
    )

    action = event.get(
        "action",
        "UNKNOWN",
    )

    execution_status = event.get(
        "execution_status",
        "UNKNOWN",
    )

    verification_status = event.get(
        "verification_status",
        "UNKNOWN",
    )

    final_state = event.get(
        "final_state",
        "UNKNOWN",
    )

    message = event.get(
        "message",
        "",
    )

    if (
        execution_status == "EXECUTED"
        and verification_status == "RECOVERED"
        and final_state == "HEALTHY"
    ):
        result = "SUCCESS"

    elif decision == "ESCALATE":
        result = "ESCALATED"

    else:
        result = "NOT SUCCESSFUL"

    return f"""
------------------------------------------------------------
RECOVERY EVENT #{event_number}
------------------------------------------------------------

Timestamp          : {timestamp}
Node               : {node}
Failure Condition  : {condition}
Confidence         : {confidence}%
Workload Healthy   : {yes_no(workload_healthy)}

Recovery Decision
------------------------------------------------------------
Decision           : {decision}
Recovery Attempt   : {attempt}
Action             : {action}

Execution & Verification
------------------------------------------------------------
Execution Status   : {execution_status}
Verification       : {verification_status}
Final State        : {final_state}
Overall Result     : {result}

Event Message
------------------------------------------------------------
{message}

"""


def build_report(events):
    lines = []

    lines.append(
        "============================================================"
    )

    lines.append(
        "              CLOUD-138 RECOVERY AUDIT REPORT"
    )

    lines.append(
        "============================================================"
    )

    lines.append("")

    lines.append(
        f"Recovery Session : {TARGET_SESSION}"
    )

    if events:

        first_node = events[0].get(
            "node",
            "UNKNOWN",
        )

        lines.append(
            f"Primary Node     : {first_node}"
        )

    else:

        lines.append(
            "Primary Node     : NO EVENTS FOUND"
        )

    lines.append("")

    lines.append(
        "Purpose"
    )

    lines.append(
        "------------------------------------------------------------"
    )

    lines.append(
        "This report presents the human-readable recovery history"
    )

    lines.append(
        "for the selected CLOUD-138 recovery session."
    )

    lines.append("")

    if not events:

        lines.append(
            "NO RECOVERY EVENTS FOUND FOR THIS SESSION."
        )

        lines.append("")

        lines.append(
            "============================================================"
        )

        return "\n".join(lines)

    successful_events = [
        event
        for event in events
        if (
            event.get("execution_status") == "EXECUTED"
            and event.get("verification_status") == "RECOVERED"
            and event.get("final_state") == "HEALTHY"
        )
    ]

    executed_events = [
        event
        for event in events
        if event.get("execution_status") == "EXECUTED"
    ]

    failed_events = [
        event
        for event in events
        if event.get("execution_status") == "FAILED"
    ]

    lines.append(
        "SESSION SUMMARY"
    )

    lines.append(
        "------------------------------------------------------------"
    )

    lines.append(
        f"Total Events      : {len(events)}"
    )

    lines.append(
        f"Executed Actions  : {len(executed_events)}"
    )

    lines.append(
        f"Successful        : {len(successful_events)}"
    )

    lines.append(
        f"Failed            : {len(failed_events)}"
    )

    lines.append("")

    for index, event in enumerate(
        events,
        start=1,
    ):

        lines.append(
            build_event_section(
                event,
                index,
            )
        )

    latest = events[-1]

    latest_success = (
        latest.get("execution_status") == "EXECUTED"
        and latest.get("verification_status") == "RECOVERED"
        and latest.get("final_state") == "HEALTHY"
    )

    lines.append(
        "============================================================"
    )

    lines.append(
        "                     FINAL RESULT"
    )

    lines.append(
        "============================================================"
    )

    lines.append("")

    lines.append(
        f"Session           : {TARGET_SESSION}"
    )

    lines.append(
        f"Node              : {latest.get('node', 'UNKNOWN')}"
    )

    lines.append(
        f"Latest Attempt    : {latest.get('attempt', 0)}"
    )

    lines.append(
        f"Condition         : {latest.get('condition', 'UNKNOWN')}"
    )

    lines.append(
        f"Decision          : {latest.get('decision', 'UNKNOWN')}"
    )

    lines.append(
        f"Execution         : {latest.get('execution_status', 'UNKNOWN')}"
    )

    lines.append(
        f"Verification      : {latest.get('verification_status', 'UNKNOWN')}"
    )

    lines.append(
        f"Final State       : {latest.get('final_state', 'UNKNOWN')}"
    )

    lines.append("")

    if latest_success:

        lines.append(
            "Recovery Status   : SUCCESS"
        )

        lines.append("")

        lines.append(
            "The failed node was automatically recovered."
        )

        lines.append(
            "The recovery command executed successfully."
        )

        lines.append(
            "Post-recovery verification confirmed that the"
        )

        lines.append(
            "Docker runtime, K3s process, Kubernetes node, and"
        )

        lines.append(
            "workload returned to a healthy state."
        )

    else:

        lines.append(
            "Recovery Status   : REVIEW REQUIRED"
        )

        lines.append("")

        lines.append(
            "The latest recovery event did not reach a fully"
        )

        lines.append(
            "verified healthy state."
        )

    lines.append("")

    lines.append(
        "============================================================"
    )

    return "\n".join(lines)


def main():

    print(
        "======================================"
    )

    print(
        " CLOUD-138 AUDIT REPORT GENERATOR"
    )

    print(
        "======================================"
    )

    print()

    print(
        f"Audit File   : {AUDIT_FILE}"
    )

    print(
        f"Session      : {TARGET_SESSION}"
    )

    print()

    events = load_events()

    print(
        f"Events Found : {len(events)}"
    )

    print()

    report = build_report(events)

    with REPORT_FILE.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as file:

        file.write(report)

        if not report.endswith("\n"):
            file.write("\n")

    print(
        "Human-readable audit report generated:"
    )

    print(
        REPORT_FILE
    )

    print()

    print(
        "Report generated successfully."
    )


if __name__ == "__main__":
    main()