"""Tests for the local UTM ROS runtime process manager."""

from __future__ import annotations

import os
import stat
import time
from pathlib import Path

from device_bridges.utm_runtime_bridge import UTMRuntimeConfig, UTMRuntimeProcessManager


def _write_fake_stack_script(path: Path) -> None:
    path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "echo fake-utm-stack-started\n"
        "trap 'exit 0' TERM INT\n"
        "while true; do sleep 0.1; done\n",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_utm_runtime_manager_starts_reports_running_and_stops(tmp_path: Path) -> None:
    script_path = tmp_path / "start_utm_vision_stack.sh"
    log_dir = tmp_path / "logs"
    _write_fake_stack_script(script_path)
    manager = UTMRuntimeProcessManager(
        UTMRuntimeConfig(
            workspace_root=tmp_path,
            script_path=script_path,
            log_dir=log_dir,
            stop_timeout_sec=1.0,
        )
    )

    started = manager.start()
    try:
        assert started["ok"] is True
        assert started["status"] == "running"
        assert started["already_running"] is False
        assert started["pid"]
        assert Path(str(started["log_path"])).parent == log_dir
        assert os.path.exists(str(started["log_path"]))

        second = manager.start()
        assert second["ok"] is True
        assert second["status"] == "running"
        assert second["already_running"] is True
        assert second["pid"] == started["pid"]

        status = manager.status()
        assert status["ok"] is True
        assert status["status"] == "running"
        assert status["pid"] == started["pid"]
    finally:
        stopped = manager.stop()

    assert stopped["ok"] is True
    assert stopped["status"] == "stopped"
    deadline = time.monotonic() + 2.0
    while manager.status()["status"] == "running" and time.monotonic() < deadline:
        time.sleep(0.05)
    assert manager.status()["status"] == "stopped"


def test_utm_runtime_manager_fails_closed_when_script_is_missing(tmp_path: Path) -> None:
    manager = UTMRuntimeProcessManager(
        UTMRuntimeConfig(
            workspace_root=tmp_path,
            script_path=tmp_path / "missing.sh",
            log_dir=tmp_path / "logs",
        )
    )

    result = manager.start()

    assert result["ok"] is False
    assert result["status"] == "error"
    assert result["failure_code"] == "UTM_RUNTIME_SCRIPT_NOT_FOUND"
    assert "missing.sh" in result["message"]
