"""Regression checks for the external UTM Vision stack shell launcher."""

from __future__ import annotations

from pathlib import Path


STACK_SCRIPT = Path("/home/lee-junyoung/yolo_ros_ws/UTM_VISION/scripts/start_utm_vision_stack.sh")


def test_stack_script_sources_ros_setup_with_nounset_disabled() -> None:
    script = STACK_SCRIPT.read_text(encoding="utf-8")

    assert "set +u" in script
    assert "source \"$setup_path\"" in script
    assert "set -u" in script
    assert script.index("set +u") < script.index("source \"$setup_path\"") < script.index("set -u")


def test_stack_script_passes_absolute_yolo_model_path() -> None:
    script = STACK_SCRIPT.read_text(encoding="utf-8")

    assert "YOLO_MODEL_PATH=" in script
    assert "model:=\"$YOLO_MODEL_PATH\"" in script
    assert "/home/lee-junyoung/yolo_ros_ws/yolov8m.pt" in script
