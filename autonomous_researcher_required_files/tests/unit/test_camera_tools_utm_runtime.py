from __future__ import annotations

from mcp_tools.camera_tools import register_camera_tools
from mcp_tools.tool_registry import ToolRegistry


def test_agent_monitoring_call_observes_utm_window() -> None:
    calls = []

    def fake_observer(**kwargs):
        calls.append(kwargs)
        return {
            "ok": True,
            "duration_sec": 5.0,
            "sample_count": 25,
            "working_count": 16,
            "not_working_count": 9,
            "unknown_count": 0,
            "initial_state": "NOT_WORKING",
            "final_state": "WORKING",
            "transition": "NOT_WORKING_TO_WORKING",
            "stable_state": "",
        }

    registry = ToolRegistry()
    register_camera_tools(registry, utm_state_observer=fake_observer)

    result = registry.call(
        "vision.equipment_cross_check",
        {
            "runtime_mode": "live",
            "checks": [
                {
                    "check_id": "utm_motion_confirm",
                    "device": "utm",
                    "intent": "monitoring",
                }
            ],
            "duration_sec": 5.0,
            "sample_interval_sec": 0.2,
            "minimum_samples": 8,
        },
    )

    assert calls == [
        {
            "duration_sec": 5.0,
            "sample_interval_sec": 0.2,
            "minimum_samples": 8,
        }
    ]
    assert result["ok"] is True
    assert result["tool"] == "vision.equipment_cross_check"
    assert result["runtime_mode"] == "live"
    assert result["results"][0]["check_id"] == "utm_motion_confirm"
    assert result["results"][0]["status"] == "verified"
    assert result["results"][0]["evidence"]["transition"] == "NOT_WORKING_TO_WORKING"


def test_agent_monitoring_call_rejects_single_sample_observation() -> None:
    def single_sample_observer(**kwargs):
        return {
            "ok": False,
            "failure_code": "UTM_INSUFFICIENT_TEMPORAL_EVIDENCE",
            "duration_sec": 5.0,
            "sample_count": 1,
            "valid_sample_count": 1,
            "transition": "INSUFFICIENT_EVIDENCE",
        }

    registry = ToolRegistry()
    register_camera_tools(registry, utm_state_observer=single_sample_observer)

    result = registry.call(
        "vision.equipment_cross_check",
        {
            "runtime_mode": "live",
            "checks": [{"check_id": "utm_motion_confirm", "device": "utm"}],
            "duration_sec": 5.0,
        },
    )

    assert result["ok"] is False
    assert result["failure_code"] == "UTM_INSUFFICIENT_TEMPORAL_EVIDENCE"
    assert result["results"][0]["status"] == "blocked"
    assert "one sample is not enough" in result["results"][0]["message"]


def test_utm_motion_confirm_rejects_stable_state_without_motion() -> None:
    def stable_observer(**kwargs):
        return {
            "ok": True,
            "duration_sec": 5.0,
            "sample_count": 20,
            "valid_sample_count": 20,
            "working_count": 0,
            "not_working_count": 20,
            "unknown_count": 0,
            "initial_state": "NOT_WORKING",
            "final_state": "NOT_WORKING",
            "transition": "STABLE_NOT_WORKING",
            "stable_state": "NOT_WORKING",
            "span_y_delta": 0.0,
        }

    registry = ToolRegistry()
    register_camera_tools(registry, utm_state_observer=stable_observer)

    result = registry.call(
        "vision.equipment_cross_check",
        {
            "runtime_mode": "live",
            "checks": [{"check_id": "utm_motion_confirm", "device": "utm"}],
        },
    )

    assert result["ok"] is False
    assert result["failure_code"] == "UTM_MOTION_NOT_CONFIRMED"
    assert result["results"][0]["status"] == "blocked"


def test_utm_test_complete_requires_export_or_software_evidence() -> None:
    def complete_observer(**kwargs):
        return {
            "ok": True,
            "duration_sec": 5.0,
            "sample_count": 20,
            "valid_sample_count": 20,
            "working_count": 18,
            "not_working_count": 2,
            "unknown_count": 0,
            "initial_state": "NOT_WORKING",
            "final_state": "WORKING",
            "transition": "NOT_WORKING_TO_WORKING",
            "stable_state": "",
            "span_y_delta": 80.0,
        }

    registry = ToolRegistry()
    register_camera_tools(registry, utm_state_observer=complete_observer)

    result = registry.call(
        "vision.equipment_cross_check",
        {
            "runtime_mode": "live",
            "checks": [{"check_id": "utm_test_complete", "device": "utm"}],
        },
    )

    assert result["ok"] is False
    assert result["failure_code"] == "UTM_TEST_COMPLETE_EVIDENCE_REQUIRED"
    assert result["results"][0]["status"] == "blocked"


def test_utm_test_complete_accepts_export_evidence_and_valid_sequence() -> None:
    def complete_observer(**kwargs):
        return {
            "ok": True,
            "duration_sec": 5.0,
            "sample_count": 20,
            "valid_sample_count": 18,
            "working_count": 16,
            "not_working_count": 2,
            "unknown_count": 2,
            "initial_state": "NOT_WORKING",
            "final_state": "WORKING",
            "transition": "NOT_WORKING_TO_WORKING",
            "stable_state": "",
            "span_y_delta": 80.0,
        }

    registry = ToolRegistry()
    register_camera_tools(registry, utm_state_observer=complete_observer)

    result = registry.call(
        "vision.equipment_cross_check",
        {
            "runtime_mode": "live",
            "checks": [{"check_id": "utm_test_complete", "device": "utm"}],
            "utm_data_ready": {"status": "ready", "result_file": "artifacts/utm/run.csv"},
        },
    )

    assert result["ok"] is True
    assert result["results"][0]["status"] == "verified"
    assert result["results"][0]["evidence"]["transition"] == "NOT_WORKING_TO_WORKING"


def test_non_live_cross_check_keeps_simulator_behavior() -> None:
    calls = []

    def fake_observer(**kwargs):
        calls.append(kwargs)
        return {"ok": True}

    registry = ToolRegistry()
    register_camera_tools(registry, utm_state_observer=fake_observer)

    result = registry.call(
        "vision.equipment_cross_check",
        {
            "runtime_mode": "test",
            "checks": [{"check_id": "utm_motion_confirm", "device": "utm"}],
        },
    )

    assert calls == []
    assert result["ok"] is True
    assert result["results"][0]["source"] == "simulator"
    assert result["results"][0]["timestamp"]
    assert result["results"][0]["expires_at"]
