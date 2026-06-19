"""Integration checks for the UTM Vision runtime GUI controls."""

from __future__ import annotations

from fastapi.testclient import TestClient

import app.main as main_module


class FakeUtmRuntimeManager:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.running = False

    def status(self) -> dict[str, object]:
        self.calls.append("status")
        return {
            "ok": True,
            "status": "running" if self.running else "stopped",
            "pid": 12345 if self.running else None,
            "message": "fake UTM runtime",
            "log_path": "/tmp/fake-utm-runtime.log",
            "command": ["/tmp/fake-start.sh"],
        }

    def start(self) -> dict[str, object]:
        self.calls.append("start")
        already_running = self.running
        self.running = True
        return {
            "ok": True,
            "status": "running",
            "already_running": already_running,
            "pid": 12345,
            "message": "fake UTM runtime started",
            "log_path": "/tmp/fake-utm-runtime.log",
            "command": ["/tmp/fake-start.sh"],
        }

    def stop(self) -> dict[str, object]:
        self.calls.append("stop")
        was_running = self.running
        self.running = False
        return {
            "ok": True,
            "status": "stopped",
            "was_running": was_running,
            "pid": None,
            "message": "fake UTM runtime stopped",
            "log_path": "/tmp/fake-utm-runtime.log",
            "command": ["/tmp/fake-start.sh"],
        }


def test_home_gui_exposes_utm_runtime_loading_controls() -> None:
    client = TestClient(main_module.app)

    page = client.get("/")

    assert page.status_code == 200
    assert "UTM Vision Runtime" in page.text
    assert "camera_rect · green_dot_monitor · YOLO" in page.text
    assert "utm-runtime-workspace-dot" in page.text
    assert "utm-runtime-workspace-detail" in page.text
    assert "btn-utm-runtime-load" in page.text
    assert "btn-utm-runtime-stop" in page.text

    script = client.get("/static/app.js")
    assert script.status_code == 200
    assert "/api/equipment/utm-runtime/status" in script.text
    assert "/api/equipment/utm-runtime/start" in script.text
    assert "/api/equipment/utm-runtime/stop" in script.text
    assert "refreshUtmRuntimeStatus" in script.text
    assert "startUtmRuntime" in script.text
    assert "utmRuntimeStatusTimer" in script.text
    assert "window.setInterval(refreshUtmRuntimeStatus" in script.text


def test_utm_runtime_api_routes_delegate_to_manager(monkeypatch) -> None:
    fake = FakeUtmRuntimeManager()
    monkeypatch.setattr(main_module, "_UTM_RUNTIME_MANAGER", fake)
    client = TestClient(main_module.app)

    status = client.get("/api/equipment/utm-runtime/status").json()
    assert status["ok"] is True
    assert status["status"] == "stopped"

    started = client.post("/api/equipment/utm-runtime/start").json()
    assert started["ok"] is True
    assert started["status"] == "running"
    assert started["already_running"] is False

    duplicate = client.post("/api/equipment/utm-runtime/start").json()
    assert duplicate["ok"] is True
    assert duplicate["already_running"] is True

    stopped = client.post("/api/equipment/utm-runtime/stop").json()
    assert stopped["ok"] is True
    assert stopped["status"] == "stopped"
    assert fake.calls == ["status", "start", "start", "stop"]
