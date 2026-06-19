"""
File purpose:
- Manage the local ROS 2 UTM Vision runtime as one start/stop subprocess.

Key classes/functions:
- UTMRuntimeConfig
- UTMRuntimeProcessManager

Inputs/outputs:
- Input: script path for launching camera_rect, green_dot_monitor, and YOLO
- Output: status dictionaries consumed by the FastAPI GUI endpoints

Dependencies:
- subprocess
- signal/os process-group control on Linux

Modification guide:
- Safe places to edit: default script/log paths and status payload fields
- Risky places to edit: process-group termination behavior
- Related files: app/main.py, web/static/app.js, web/templates/index.html
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
from typing import Any


@dataclass(frozen=True)
class UTMRuntimeConfig:
    """Configuration for the local UTM Vision ROS stack launcher."""

    workspace_root: Path
    script_path: Path
    log_dir: Path
    stop_timeout_sec: float = 5.0

    @classmethod
    def from_devices_config(
        cls,
        devices_config: dict[str, Any],
        *,
        repo_root: Path,
    ) -> "UTMRuntimeConfig":
        """Build config from configs/devices.yaml with stable local defaults."""
        devices = devices_config.get("devices", devices_config)
        raw = devices.get("utm_vision_runtime", {}) if isinstance(devices, dict) else {}
        workspace_root = Path(
            str(raw.get("workspace_root") or "/home/lee-junyoung/yolo_ros_ws/UTM_VISION")
        ).expanduser()
        script_path = Path(
            str(raw.get("script_path") or workspace_root / "scripts" / "start_utm_vision_stack.sh")
        ).expanduser()
        if not script_path.is_absolute():
            script_path = workspace_root / script_path
        log_dir = Path(str(raw.get("log_dir") or repo_root / "artifacts" / "utm_runtime")).expanduser()
        if not log_dir.is_absolute():
            log_dir = repo_root / log_dir
        try:
            stop_timeout_sec = float(raw.get("stop_timeout_sec", 5.0))
        except (TypeError, ValueError):
            stop_timeout_sec = 5.0
        return cls(
            workspace_root=workspace_root,
            script_path=script_path,
            log_dir=log_dir,
            stop_timeout_sec=max(stop_timeout_sec, 0.5),
        )


class UTMRuntimeProcessManager:
    """Start, stop, and report the local UTM Vision ROS process group."""

    def __init__(self, config: UTMRuntimeConfig) -> None:
        self.config = UTMRuntimeConfig(
            workspace_root=Path(config.workspace_root).expanduser(),
            script_path=Path(config.script_path).expanduser(),
            log_dir=Path(config.log_dir).expanduser(),
            stop_timeout_sec=float(config.stop_timeout_sec),
        )
        self._lock = threading.Lock()
        self._process: subprocess.Popen[bytes] | None = None
        self._started_at: str = ""
        self._started_monotonic: float = 0.0
        self._last_log_path: Path | None = None

    def start(self) -> dict[str, object]:
        """Launch the configured UTM Vision stack unless it is already running."""
        with self._lock:
            if self._is_running_locked():
                payload = self._status_locked()
                payload["already_running"] = True
                payload["message"] = "UTM Vision runtime is already running."
                return payload
            if not self.config.script_path.is_file():
                return self._error_payload(
                    "UTM_RUNTIME_SCRIPT_NOT_FOUND",
                    f"UTM runtime script not found: {self.config.script_path}",
                )
            self.config.log_dir.mkdir(parents=True, exist_ok=True)
            self.config.workspace_root.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            log_path = self.config.log_dir / f"utm_runtime_{stamp}.log"
            command = ["bash", str(self.config.script_path)]
            env = os.environ.copy()
            env.setdefault("PYTHONUNBUFFERED", "1")
            try:
                with log_path.open("ab", buffering=0) as log_file:
                    self._process = subprocess.Popen(
                        command,
                        cwd=str(self.config.workspace_root),
                        env=env,
                        stdout=log_file,
                        stderr=subprocess.STDOUT,
                        start_new_session=True,
                    )
            except OSError as exc:
                return self._error_payload("UTM_RUNTIME_START_FAILED", str(exc))
            self._started_at = datetime.now(timezone.utc).isoformat()
            self._started_monotonic = time.monotonic()
            self._last_log_path = log_path
            payload = self._status_locked()
            payload["already_running"] = False
            payload["message"] = "UTM Vision runtime started."
            return payload

    def stop(self) -> dict[str, object]:
        """Terminate the managed UTM Vision process group."""
        with self._lock:
            process = self._process
            if process is None or process.poll() is not None:
                self._process = None
                payload = self._status_locked()
                payload["was_running"] = False
                payload["message"] = "UTM Vision runtime was not running."
                return payload
            pid = process.pid
            try:
                self._terminate_process_group(process, signal.SIGTERM)
                process.wait(timeout=self.config.stop_timeout_sec)
            except subprocess.TimeoutExpired:
                self._terminate_process_group(process, signal.SIGKILL)
                process.wait(timeout=max(self.config.stop_timeout_sec, 0.5))
            finally:
                self._process = None
            return {
                "ok": True,
                "status": "stopped",
                "pid": None,
                "previous_pid": pid,
                "was_running": True,
                "returncode": process.returncode,
                "started_at": self._started_at,
                "log_path": str(self._last_log_path or ""),
                "command": self._command_preview(),
                "message": "UTM Vision runtime stopped.",
            }

    def status(self) -> dict[str, object]:
        """Return the latest process status without mutating external state."""
        with self._lock:
            return self._status_locked()

    def shutdown(self) -> dict[str, object]:
        """Release the process group during application shutdown."""
        return self.stop()

    def _status_locked(self) -> dict[str, object]:
        process = self._process
        if process is None:
            return {
                "ok": True,
                "status": "stopped",
                "pid": None,
                "returncode": None,
                "started_at": self._started_at,
                "log_path": str(self._last_log_path or ""),
                "command": self._command_preview(),
                "message": "UTM Vision runtime is stopped.",
            }
        returncode = process.poll()
        if returncode is None:
            return {
                "ok": True,
                "status": "running",
                "pid": process.pid,
                "returncode": None,
                "started_at": self._started_at,
                "uptime_sec": max(time.monotonic() - self._started_monotonic, 0.0)
                if self._started_monotonic
                else None,
                "log_path": str(self._last_log_path or ""),
                "command": self._command_preview(),
                "message": "UTM Vision runtime is running.",
            }
        ok = returncode == 0
        return {
            "ok": ok,
            "status": "stopped" if ok else "error",
            "pid": None,
            "returncode": returncode,
            "started_at": self._started_at,
            "log_path": str(self._last_log_path or ""),
            "command": self._command_preview(),
            "failure_code": "" if ok else "UTM_RUNTIME_EXITED",
            "message": "UTM Vision runtime exited." if ok else "UTM Vision runtime exited with an error.",
        }

    def _is_running_locked(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def _command_preview(self) -> list[str]:
        return ["bash", str(self.config.script_path)]

    def _error_payload(self, failure_code: str, message: str) -> dict[str, object]:
        return {
            "ok": False,
            "status": "error",
            "pid": None,
            "returncode": None,
            "started_at": self._started_at,
            "log_path": str(self._last_log_path or ""),
            "command": self._command_preview(),
            "failure_code": failure_code,
            "message": message,
        }

    @staticmethod
    def _terminate_process_group(process: subprocess.Popen[bytes], sig: signal.Signals) -> None:
        try:
            os.killpg(os.getpgid(process.pid), sig)
        except ProcessLookupError:
            return
        except OSError:
            process.send_signal(sig)
