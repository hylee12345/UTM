from __future__ import annotations

from device_bridges.utm_state_observer import summarize_utm_state_sequence


def test_observer_detects_not_working_to_working_transition() -> None:
    samples = [
        {"state": "NOT_WORKING", "span_y": 310.0, "marker_count": 2},
        {"state": "NOT_WORKING", "span_y": 305.0, "marker_count": 2},
        {"state": "NOT_WORKING", "span_y": 295.0, "marker_count": 2},
        {"state": "WORKING", "span_y": 245.0, "marker_count": 2},
        {"state": "WORKING", "span_y": 240.0, "marker_count": 2},
        {"state": "WORKING", "span_y": 238.0, "marker_count": 2},
    ]

    result = summarize_utm_state_sequence(samples, minimum_samples=6)

    assert result["ok"] is True
    assert result["transition"] == "NOT_WORKING_TO_WORKING"
    assert result["initial_state"] == "NOT_WORKING"
    assert result["final_state"] == "WORKING"


def test_observer_fails_closed_for_single_sample() -> None:
    result = summarize_utm_state_sequence(
        [{"state": "WORKING", "span_y": 240.0, "marker_count": 2}],
        minimum_samples=6,
    )

    assert result["ok"] is False
    assert result["failure_code"] == "UTM_INSUFFICIENT_TEMPORAL_EVIDENCE"


def test_observer_collects_multiple_samples_before_summarizing() -> None:
    captured_samples = [
        {"state": "NOT_WORKING", "span_y": 310.0, "point_count": 2},
        {"state": "NOT_WORKING", "span_y": 306.0, "point_count": 2},
        {"state": "NOT_WORKING", "span_y": 302.0, "point_count": 2},
        {"state": "WORKING", "span_y": 246.0, "point_count": 2},
        {"state": "WORKING", "span_y": 243.0, "point_count": 2},
        {"state": "WORKING", "span_y": 239.0, "point_count": 2},
    ]

    result = summarize_utm_state_sequence(captured_samples, minimum_samples=6)

    assert result["sample_count"] == 6
    assert result["valid_sample_count"] == 6
    assert result["transition"] == "NOT_WORKING_TO_WORKING"
    assert result["span_y_delta"] == 71.0
