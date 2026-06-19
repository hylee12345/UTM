"""
File purpose:
- MCP tool wrapper for camera operations.

Key classes/functions:
- register_camera_tools

Inputs/outputs:
- Input: ToolRegistry
- Output: camera tool handlers registered

Dependencies:
- mcp_tools.tool_registry.ToolRegistry

Modification guide:
- Safe places to edit: payload schema and response fields
- Risky places to edit: tool names consumed by vision agent
- Related files: agents/vision_agent.py, device_bridges/realsense_bridge.py
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from mcp_tools.tool_registry import ToolRegistry


UTM_CHECK_IDS = {"utm_pre_start", "utm_motion_confirm", "utm_test_complete"}
UTM_MOTION_TRANSITIONS = {"NOT_WORKING_TO_WORKING", "WORKING_TO_NOT_WORKING"}
MEANINGFUL_SPAN_Y_DELTA_PX = 10.0
UtmStateObserver = Callable[..., dict[str, Any]]


def _camera_capture(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "tool": "camera.capture",
        "frame_id": payload.get("frame_id", "mock"),
        "observation_id": f"obs-{payload.get('frame_id', 'mock')}",
        "camera_key": payload.get("camera_key", "top"),
        "purpose": payload.get("purpose", "3dp_output_pickup_check"),
        "source": "simulator",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stable_for_ms": 1200,
        "confidence": 0.86,
        "pose_confidence": 0.86,
        "anomaly": False,
    }


def _is_utm_check(item: dict[str, Any]) -> bool:
    return str(item.get("check_id", "")) in UTM_CHECK_IDS or str(item.get("device", "")).lower() == "utm"


def _utm_failure_result(check_id: str, observation: dict[str, Any]) -> dict[str, Any]:
    failure_code = str(observation.get("failure_code") or "UTM_OBSERVATION_FAILED")
    message = (
        "UTM vision requires a time-windowed observation; one sample is not enough."
        if failure_code == "UTM_INSUFFICIENT_TEMPORAL_EVIDENCE"
        else "UTM vision observation did not provide enough reliable evidence."
    )
    return {
        "agent_signal_type": "equipment_vision_check_result",
        "check_id": check_id,
        "ok": False,
        "confidence": 0.0,
        "signals": {"simulated_or_external_check": False, "anomaly": True},
        "status": "blocked",
        "failure_code": failure_code,
        "message": message,
        "evidence": observation,
        "source": "utm_vision",
    }


def _utm_success_result(check_id: str, observation: dict[str, Any]) -> dict[str, Any]:
    transition = str(observation.get("transition") or observation.get("stable_state") or "UNKNOWN")
    duration_sec = float(observation.get("duration_sec") or 0.0)
    return {
        "agent_signal_type": "equipment_vision_check_result",
        "check_id": check_id,
        "ok": True,
        "confidence": 0.95,
        "signals": {"simulated_or_external_check": True, "anomaly": False},
        "status": "verified",
        "message": f"UTM vision observed {transition} over {duration_sec:.1f}s",
        "evidence": {
            "duration_sec": duration_sec,
            "sample_count": observation.get("sample_count", 0),
            "transition": observation.get("transition", ""),
            "stable_state": observation.get("stable_state", ""),
            "initial_state": observation.get("initial_state", ""),
            "final_state": observation.get("final_state", ""),
            "working_count": observation.get("working_count", 0),
            "not_working_count": observation.get("not_working_count", 0),
            "unknown_count": observation.get("unknown_count", 0),
            "span_y_delta": observation.get("span_y_delta", 0.0),
        },
        "source": "utm_vision",
    }


def _has_marker_reliability(observation: dict[str, Any]) -> bool:
    sample_count = int(observation.get("sample_count") or 0)
    valid_sample_count = int(observation.get("valid_sample_count") or sample_count)
    if sample_count <= 0:
        return False
    return valid_sample_count / sample_count >= 0.8


def _has_motion_evidence(observation: dict[str, Any]) -> bool:
    transition = str(observation.get("transition") or "")
    try:
        span_y_delta = float(observation.get("span_y_delta") or 0.0)
    except (TypeError, ValueError):
        span_y_delta = 0.0
    return transition in UTM_MOTION_TRANSITIONS or span_y_delta >= MEANINGFUL_SPAN_Y_DELTA_PX


def _unknown_dominated(observation: dict[str, Any]) -> bool:
    sample_count = int(observation.get("sample_count") or 0)
    unknown_count = int(observation.get("unknown_count") or 0)
    return sample_count > 0 and unknown_count > sample_count / 2


def _iter_evidence_dicts(payload: dict[str, Any]):
    yield payload
    for key in ("utm_data_ready", "equipment_handoff", "equipment_result", "equipment_report"):
        value = payload.get(key)
        if isinstance(value, dict):
            yield value

    source_stage_context = payload.get("source_stage_context")
    if isinstance(source_stage_context, dict):
        yield source_stage_context
        for key in ("equipment", "utm_data_ready", "equipment_handoff", "equipment_result", "equipment_report"):
            value = source_stage_context.get(key)
            if isinstance(value, dict):
                yield value


def _has_utm_completion_evidence(payload: dict[str, Any]) -> bool:
    if payload.get("utm_software_evidence"):
        return True
    ready_statuses = {"ready", "ready_for_analysis", "verified_complete", "complete", "completed"}
    path_keys = {"result_file", "utm_csv_path", "linux_path", "windows_path", "local_path", "path"}
    for item in _iter_evidence_dicts(payload):
        status = str(item.get("status") or item.get("handoff_status") or "").lower()
        if status in ready_statuses:
            return True
        if any(str(item.get(key) or "") for key in path_keys):
            return True
        data_ledger = item.get("data_ledger")
        if isinstance(data_ledger, dict) and data_ledger.get("parse_ready"):
            return True
        save_export = item.get("save_export")
        if isinstance(save_export, dict) and save_export.get("ok"):
            return True
        if item.get("save_export_responsibility_ok"):
            return True
    return False


def _blocked_utm_result(
    check_id: str,
    observation: dict[str, Any],
    *,
    failure_code: str,
) -> dict[str, Any]:
    blocked_observation = dict(observation)
    blocked_observation["ok"] = False
    blocked_observation["failure_code"] = failure_code
    return _utm_failure_result(check_id, blocked_observation)


def _map_utm_observation_to_cross_check(
    check_id: str,
    observation: dict[str, Any],
    *,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if not observation.get("ok"):
        return _utm_failure_result(check_id, observation)
    if check_id == "utm_pre_start" and not _has_marker_reliability(observation):
        return _blocked_utm_result(
            check_id,
            observation,
            failure_code="UTM_MARKER_DETECTION_NOT_RELIABLE",
        )
    if check_id == "utm_motion_confirm" and not _has_motion_evidence(observation):
        return _blocked_utm_result(
            check_id,
            observation,
            failure_code="UTM_MOTION_NOT_CONFIRMED",
        )
    if check_id == "utm_test_complete":
        if _unknown_dominated(observation):
            return _blocked_utm_result(
                check_id,
                observation,
                failure_code="UTM_UNKNOWN_DOMINATED",
            )
        if not _has_utm_completion_evidence(payload):
            return _blocked_utm_result(
                check_id,
                observation,
                failure_code="UTM_TEST_COMPLETE_EVIDENCE_REQUIRED",
            )
    return _utm_success_result(check_id, observation)


def _simulated_equipment_cross_check(payload: dict[str, Any]) -> dict[str, Any]:
    checks = payload.get("checks") if isinstance(payload.get("checks"), list) else []
    mode = str(payload.get("runtime_mode") or payload.get("mode") or "test")
    confidence = float(payload.get("confidence", 0.9 if mode != "live" else 0.0))
    ok_default = bool(payload.get("force_ok", mode != "live"))
    ttl_ms = int(payload.get("freshness_ttl_ms") or payload.get("ttl_ms") or 5000)
    timestamp = datetime.now(timezone.utc)
    expires_at = timestamp + timedelta(milliseconds=max(1, ttl_ms))
    results = []
    for item in checks:
        if not isinstance(item, dict) or not item.get("check_id"):
            continue
        check_id = str(item["check_id"])
        ok = ok_default
        results.append(
            {
                "agent_signal_type": "equipment_vision_check_result",
                "check_id": check_id,
                "ok": ok,
                "confidence": confidence if ok else 0.0,
                "signals": {"simulated_or_external_check": ok, "anomaly": False},
                "evidence": {"observation_id": f"obs-{check_id}", "frame_ids": [f"frame-{check_id}"] if ok else []},
                "timestamp": timestamp.isoformat(),
                "expires_at": expires_at.isoformat(),
                "freshness_ttl_ms": ttl_ms,
                "source": "simulator" if mode != "live" else "live_required_external_vision",
            }
        )
    return {
        "ok": bool(results) and all(item.get("ok") for item in results),
        "tool": "vision.equipment_cross_check",
        "runtime_mode": mode,
        "results": results,
        "failure_code": None if results and all(item.get("ok") for item in results) else "VISION_EQUIPMENT_CROSS_CHECK_REQUIRED",
    }


def _equipment_cross_check(
    payload: dict[str, Any],
    *,
    utm_state_observer: UtmStateObserver | None = None,
) -> dict[str, Any]:
    checks = payload.get("checks") if isinstance(payload.get("checks"), list) else []
    mode = str(payload.get("runtime_mode") or payload.get("mode") or "test")
    duration_sec = float(payload.get("duration_sec") or 5.0)
    sample_interval_sec = float(payload.get("sample_interval_sec") or 0.2)
    minimum_samples = int(payload.get("minimum_samples") or 8)

    utm_checks = [
        item
        for item in checks
        if isinstance(item, dict) and item.get("check_id") and _is_utm_check(item)
    ]
    if mode == "live" and utm_state_observer is not None and utm_checks:
        results = []
        for item in utm_checks:
            observation = utm_state_observer(
                duration_sec=duration_sec,
                sample_interval_sec=sample_interval_sec,
                minimum_samples=minimum_samples,
            )
            results.append(_map_utm_observation_to_cross_check(str(item["check_id"]), observation, payload=payload))
        ok = bool(results) and all(item.get("ok") for item in results)
        return {
            "ok": ok,
            "tool": "vision.equipment_cross_check",
            "runtime_mode": mode,
            "results": results,
            "failure_code": None if ok else results[0].get("failure_code"),
        }

    return _simulated_equipment_cross_check(payload)


def register_camera_tools(
    registry: ToolRegistry,
    *,
    utm_state_observer: UtmStateObserver | None = None,
) -> None:
    """Register camera capture and equipment cross-check tools."""
    registry.register("camera.capture", _camera_capture)
    registry.register(
        "vision.equipment_cross_check",
        lambda payload: _equipment_cross_check(payload, utm_state_observer=utm_state_observer),
    )
