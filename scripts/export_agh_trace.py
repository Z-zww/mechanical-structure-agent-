"""Export a minimal, sanitized AGH execution trace for contest submission.

The exporter reads AGH's local sessions database but intentionally excludes
prompts, model output, file paths, credentials, and large tool payloads. The
result is evidence of orchestration and outcomes, not a replacement for the
full private AGH audit database.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any


TOOL_EVENT_TYPES = {"tool/call", "tool/result"}
SUMMARY_KEYS = (
    "ok",
    "status",
    "error_code",
    "formula_version",
    "search_version",
    "sensitivity_version",
    "tolerance_version",
    "validation_type",
    "failed_constraints",
)
REGISTERED_TOOLS = (
    "calculate_cantilever",
    "calculate_hollow_cantilever",
    "search_hollow_design_candidates",
    "search_design_candidates",
    "analyze_design_sensitivity",
    "analyze_hollow_design_sensitivity",
    "verify_manufacturing_tolerance",
    "verify_hollow_manufacturing_tolerance",
    "generate_design_dossier",
    "fe_beam_cantilever",
)


def _json(value: str) -> Any:
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return None


def _result_summary(event: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "is_error": bool(event.get("isError", False)),
    }
    if event.get("code"):
        summary["code"] = event["code"]
    content = event.get("content")
    text = ""
    if isinstance(content, list):
        text = " ".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        )
    parsed = _json(text)
    if isinstance(parsed, dict):
        for key in SUMMARY_KEYS:
            if key in parsed:
                summary[key] = parsed[key]
    elif text.lstrip().lower().startswith("<!doctype html"):
        summary["artifact"] = "html"
    elif text.lstrip().startswith("#"):
        summary["artifact"] = "markdown"
    elif text:
        summary["message_class"] = "text"
    return summary


def _event_line(seq: int, timestamp: str, event_type: str, data: str) -> dict[str, Any]:
    event = _json(data) or {}
    output: dict[str, Any] = {
        "seq": seq,
        "at": timestamp,
        "type": event_type,
    }
    if event_type == "tool/call":
        args = event.get("args")
        output.update(
            {
                "tool": event.get("name", "unknown"),
                "ordinal": event.get("ordinal"),
                "argument_keys": sorted(args) if isinstance(args, dict) else [],
            }
        )
    else:
        output.update(_result_summary(event))
    return output


def export_trace(database: Path, session_key: str, destination: Path) -> None:
    connection = sqlite3.connect(database)
    try:
        rows = connection.execute(
            "SELECT seq, ts, type, data FROM events "
            "WHERE session_key = ? AND type IN ('tool/call', 'tool/result') "
            "ORDER BY seq",
            (session_key,),
        ).fetchall()
    finally:
        connection.close()
    if not rows:
        raise SystemExit(f"no tool events found for session: {session_key}")

    session_digest = hashlib.sha256(session_key.encode("utf-8")).hexdigest()[:16]
    calls = sum(event_type == "tool/call" for _, _, event_type, _ in rows)
    results = sum(event_type == "tool/result" for _, _, event_type, _ in rows)
    lines: list[dict[str, Any]] = [
        {
            "trace_version": "agh-trace-sanitized-v1",
            "source": "AGH local sessions event export",
            "session_digest": session_digest,
            "event_counts": {"tool_call": calls, "tool_result": results},
            "registered_tools": list(REGISTERED_TOOLS),
            "redactions": [
                "session key, prompts, model output, file paths, credentials, and raw payloads",
                "tool arguments are represented by field names only",
            ],
            "limitations": [
                "This is an evidence trace of orchestration outcomes, not the full AGH audit database.",
                "Reproduction uses the versioned cases and scripts in the repository.",
            ],
        }
    ]
    lines.extend(_event_line(seq, ts, event_type, data) for seq, ts, event_type, data in rows)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        "\n".join(json.dumps(line, ensure_ascii=False, separators=(",", ":")) for line in lines)
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True, help="AGH sessions.db path")
    parser.add_argument("--session", required=True, help="AGH session key to export")
    parser.add_argument("--output", type=Path, required=True, help="sanitized JSONL output")
    args = parser.parse_args()
    export_trace(args.database, args.session, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
