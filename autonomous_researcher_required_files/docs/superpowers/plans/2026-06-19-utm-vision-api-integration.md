# UTM Vision API Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect `/home/lee-junyoung/yolo_ros_ws/UTM_VISION` to `autonomous_researcher` through the main GUI so the operator can start, stop, monitor, and later use UTM vision state as time-windowed equipment evidence.

**Architecture:** Keep ROS 2 execution outside the Python web runtime. The `autonomous_researcher` FastAPI server exposes a small runtime-control API, owns a subprocess manager, and starts one shell script that launches `camera_rect`, `green_dot_monitor`, and `yolo` as a single process group. UTM state judgment must not use a single image sample; the data-integration phase must observe `/compression_tester/summary` continuously for a short time window and decide from the observed state sequence.

**Tech Stack:** FastAPI, vanilla browser JavaScript, Python `subprocess`, ROS 2 Lyrical, `usb_cam`, `image_proc`, `compression_tester_monitor`, `yolo_bringup`, pytest.

---

## Status

This plan supersedes the earlier ROS-side FastAPI design. We did not add a separate FastAPI server inside the ROS package. The current working approach is:

```text
Main GUI Loading button
  -> web/static/app.js
  -> POST /api/equipment/utm-runtime/start
  -> device_bridges.utm_runtime_bridge.UTMRuntimeProcessManager
  -> /home/lee-junyoung/yolo_ros_ws/UTM_VISION/scripts/start_utm_vision_stack.sh
  -> camera_rect + green_dot_monitor + yolo
```

Stop flow:

```text
Main GUI Stop button
  -> POST /api/equipment/utm-runtime/stop
  -> terminate the managed process group
  -> camera_rect, green_dot_monitor, and yolo stop together
```

Current runtime-control API:

```text
GET  /api/equipment/utm-runtime/status
POST /api/equipment/utm-runtime/start
POST /api/equipment/utm-runtime/stop
```

Current ROS outputs:

```text
/camera/image_raw
/camera/image_rect
/image_utm
/compression_tester/summary
/compression_tester/state
/compression_tester/metrics
/compression_tester/green_points
/yolo/detections
/yolo/tracking
/yolo/dbg_image
```

Important monitoring rule:

```text
Do not decide UTM working/not_working from one image sample.
Observe several seconds of /compression_tester/summary samples.
Use the sequence to detect whether NOT_WORKING stays NOT_WORKING,
WORKING stays WORKING, or NOT_WORKING transitions into WORKING.
```

Agent function-calling flow:

```text
User input: "UTM 모니터링해" or "모니터링해"
  -> Equipment/Vision agent selects tool/function call
  -> ToolRegistry.call("vision.equipment_cross_check", payload)
  -> mcp_tools.camera_tools._equipment_cross_check(payload)
  -> device_bridges.utm_state_observer.observe_utm_state_window(duration_sec=5.0, sample_interval_sec=0.2, minimum_samples=8)
  -> ros2 topic echo /compression_tester/summary --once --field data, repeated for duration_sec
  -> summarize_utm_state_sequence(samples)
  -> return structured JSON result to the agent
  -> agent explains the observed UTM state to the user
```

The runtime-control API only starts and stops the ROS stack. The monitoring decision must be returned by the agent-callable tool. The intended function-call payload is:

```json
{
  "runtime_mode": "live",
  "checks": [
    {
      "check_id": "utm_motion_confirm",
      "device": "utm",
      "intent": "monitoring"
    }
  ],
  "duration_sec": 5.0,
  "sample_interval_sec": 0.2,
  "minimum_samples": 8
}
```

Expected successful return shape:

```json
{
  "ok": true,
  "tool": "vision.equipment_cross_check",
  "runtime_mode": "live",
  "results": [
    {
      "check_id": "utm_motion_confirm",
      "ok": true,
      "status": "verified",
      "message": "UTM vision observed NOT_WORKING_TO_WORKING over 5.0s",
      "evidence": {
        "duration_sec": 5.0,
        "sample_count": 25,
        "transition": "NOT_WORKING_TO_WORKING",
        "initial_state": "NOT_WORKING",
        "final_state": "WORKING"
      }
    }
  ]
}
```

If the agent or API tries to judge from one sample, the function must fail closed:

```json
{
  "ok": false,
  "tool": "vision.equipment_cross_check",
  "runtime_mode": "live",
  "failure_code": "UTM_INSUFFICIENT_TEMPORAL_EVIDENCE",
  "message": "UTM vision requires a time-windowed observation; one sample is not enough."
}
```

## File Structure

### autonomous_researcher

- Create: `device_bridges/utm_state_observer.py`
  - Implements `observe_utm_state_window()` for live monitoring.
  - Reads `/compression_tester/summary` repeatedly.
  - Summarizes multi-sample state sequences into stable/transition/insufficient-evidence results.
  - Does not make one-image decisions.

- Create: `device_bridges/utm_runtime_bridge.py`
  - Owns `UTMRuntimeConfig` and `UTMRuntimeProcessManager`.
  - Starts the stack script with `subprocess.Popen(..., start_new_session=True)`.
  - Stops the full process group with `SIGTERM`, then `SIGKILL` if needed.
  - Returns status dictionaries for the GUI API.

- Modify: `app/main.py`
  - Imports the UTM runtime manager.
  - Adds singleton `_UTM_RUNTIME_MANAGER`.
  - Adds `_utm_runtime_manager()`.
  - Adds `/api/equipment/utm-runtime/status`.
  - Adds `/api/equipment/utm-runtime/start`.
  - Adds `/api/equipment/utm-runtime/stop`.
  - Stops the UTM process group on FastAPI shutdown.

- Modify: `mcp_tools/camera_tools.py`
  - Keeps `vision.equipment_cross_check` as the agent function-call surface.
  - Detects live UTM check IDs such as `utm_motion_confirm`.
  - Calls `observe_utm_state_window()` and maps the result into the existing equipment cross-check response shape.
  - Fails closed with `UTM_INSUFFICIENT_TEMPORAL_EVIDENCE` when the observation window has too few valid samples.

- Modify: `app/bootstrap.py`
  - Wires the live UTM observer into `register_camera_tools()`.
  - Keeps simulator behavior unchanged when live UTM monitoring is disabled.

- Modify: `configs/devices.yaml`
  - Adds `devices.utm_vision_runtime`.
  - Stores `workspace_root`, `script_path`, `log_dir`, and `stop_timeout_sec`.

- Modify: `web/templates/index.html`
  - Adds the `UTM Vision Runtime` workspace card.
  - Adds `Loading` and `Stop` buttons.
  - Bumps `/static/app.js` query version to avoid stale browser cache.

- Modify: `web/static/app.js`
  - Adds UTM runtime DOM handles.
  - Adds `refreshUtmRuntimeStatus()`.
  - Adds `startUtmRuntime()`.
  - Adds `stopUtmRuntime()`.
  - Adds `utmRuntimeStatusTimer` polling so an already-open GUI updates after runtime state changes.

- Create: `tests/unit/test_utm_runtime_bridge.py`
  - Tests process manager start/status/stop with a fake shell script.
  - Tests fail-closed behavior when the configured script is missing.

- Create: `tests/unit/test_utm_runtime_stack_script.py`
  - Tests the external stack script disables shell nounset around ROS setup sourcing.
  - Tests the script passes an absolute YOLO model path.

- Create: `tests/integration/test_utm_runtime_gui_api.py`
  - Tests the main GUI exposes the UTM runtime card and buttons.
  - Tests JS references the runtime API endpoints.
  - Tests FastAPI routes delegate to the runtime manager.

- Create: `tests/unit/test_utm_state_observer.py`
  - Tests time-window summarization.
  - Tests `NOT_WORKING_TO_WORKING` transition detection.
  - Tests single-sample failure with `UTM_INSUFFICIENT_TEMPORAL_EVIDENCE`.

- Create: `tests/unit/test_camera_tools_utm_runtime.py`
  - Tests the agent function-call payload path through `vision.equipment_cross_check`.
  - Tests the observer result mapping.
  - Tests simulator behavior stays unchanged for non-live/non-UTM checks.

- Create: `docs/hardware/utm_vision_runtime_gui.md`
  - Documents the GUI card, endpoints, configuration, and log directory.

### UTM_VISION ROS Workspace

- Create: `/home/lee-junyoung/yolo_ros_ws/UTM_VISION/scripts/start_utm_vision_stack.sh`
  - Sources ROS and workspace setup files.
  - Starts `camera_rect`.
  - Starts `green_dot_monitor`.
  - Starts YOLO with `model:=/home/lee-junyoung/yolo_ros_ws/yolov8m.pt`, `input_image_topic:=/image_utm`, `classes:=0`, and `threshold:=0.7`.
  - Traps `INT` and `TERM` and stops all child processes together.

- Modify: `/home/lee-junyoung/yolo_ros_ws/UTM_VISION/README.md`
  - Documents the one-shot stack script and the GUI/API launch path.

## Task 1: Add the UTM Runtime Process Manager

**Files:**
- Create: `device_bridges/utm_runtime_bridge.py`
- Test: `tests/unit/test_utm_runtime_bridge.py`

- [x] **Step 1: Write the failing process-manager tests**

Create `tests/unit/test_utm_runtime_bridge.py` with tests that expect this import:

```python
from device_bridges.utm_runtime_bridge import UTMRuntimeConfig, UTMRuntimeProcessManager
```

The tests create a fake long-running shell script, start it through `UTMRuntimeProcessManager`, assert `status == "running"`, call `stop()`, and assert `status == "stopped"`.

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/unit/test_utm_runtime_bridge.py -q
```

Expected red result before implementation:

```text
ModuleNotFoundError: No module named 'device_bridges.utm_runtime_bridge'
```

- [x] **Step 2: Implement `UTMRuntimeConfig`**

Add a dataclass with these fields:

```python
@dataclass(frozen=True)
class UTMRuntimeConfig:
    workspace_root: Path
    script_path: Path
    log_dir: Path
    stop_timeout_sec: float = 5.0
```

Add `from_devices_config()` so `configs/devices.yaml` can override paths while defaulting to:

```text
workspace_root=/home/lee-junyoung/yolo_ros_ws/UTM_VISION
script_path=/home/lee-junyoung/yolo_ros_ws/UTM_VISION/scripts/start_utm_vision_stack.sh
log_dir=<autonomous_researcher>/artifacts/utm_runtime
```

- [x] **Step 3: Implement `UTMRuntimeProcessManager`**

The manager provides:

```python
start() -> dict[str, object]
stop() -> dict[str, object]
status() -> dict[str, object]
shutdown() -> dict[str, object]
```

`start()` runs:

```python
subprocess.Popen(
    ["bash", str(self.config.script_path)],
    cwd=str(self.config.workspace_root),
    env=env,
    stdout=log_file,
    stderr=subprocess.STDOUT,
    start_new_session=True,
)
```

`stop()` terminates the process group:

```python
os.killpg(os.getpgid(process.pid), signal.SIGTERM)
```

If the process does not stop within `stop_timeout_sec`, send `SIGKILL`.

- [x] **Step 4: Verify process manager tests**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/unit/test_utm_runtime_bridge.py -q
```

Expected green result:

```text
2 passed
```

## Task 2: Add FastAPI Runtime-Control Endpoints

**Files:**
- Modify: `app/main.py`
- Modify: `configs/devices.yaml`
- Test: `tests/integration/test_utm_runtime_gui_api.py`

- [x] **Step 1: Write failing GUI/API tests**

Create `tests/integration/test_utm_runtime_gui_api.py` with a fake manager:

```python
class FakeUtmRuntimeManager:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.running = False

    def status(self) -> dict[str, object]:
        self.calls.append("status")
        return {"ok": True, "status": "running" if self.running else "stopped"}

    def start(self) -> dict[str, object]:
        self.calls.append("start")
        already_running = self.running
        self.running = True
        return {"ok": True, "status": "running", "already_running": already_running}

    def stop(self) -> dict[str, object]:
        self.calls.append("stop")
        self.running = False
        return {"ok": True, "status": "stopped"}
```

The tests monkeypatch `app.main._UTM_RUNTIME_MANAGER`, then call:

```text
GET  /api/equipment/utm-runtime/status
POST /api/equipment/utm-runtime/start
POST /api/equipment/utm-runtime/stop
```

Expected red result before implementation:

```text
AttributeError: app.main has no attribute '_UTM_RUNTIME_MANAGER'
```

- [x] **Step 2: Add singleton manager helper**

In `app/main.py`, add:

```python
_UTM_RUNTIME_MANAGER: UTMRuntimeProcessManager | None = None

def _utm_runtime_manager() -> UTMRuntimeProcessManager:
    global _UTM_RUNTIME_MANAGER
    if _UTM_RUNTIME_MANAGER is None:
        cfg = load_all_configs(resolve_path("configs"))
        config = UTMRuntimeConfig.from_devices_config(
            cfg.get("devices", {}),
            repo_root=resolve_path("."),
        )
        _UTM_RUNTIME_MANAGER = UTMRuntimeProcessManager(config)
    return _UTM_RUNTIME_MANAGER
```

- [x] **Step 3: Add endpoints**

Add:

```python
@app.get("/api/equipment/utm-runtime/status")
async def get_utm_runtime_status() -> dict[str, object]:
    return _utm_runtime_manager().status()
```

Add:

```python
@app.post("/api/equipment/utm-runtime/start")
async def post_utm_runtime_start() -> dict[str, object]:
    result = _utm_runtime_manager().start()
    await controller.emit_workspace_result(
        workspace="equipment",
        tool="equipment.utm_runtime.start",
        result=result,
        stage=Stage.EQUIPMENT,
        module_id="equipment",
        agent="equipment_agent",
        workflow="utm_vision_runtime",
        node_event=True,
    )
    return result
```

Add:

```python
@app.post("/api/equipment/utm-runtime/stop")
async def post_utm_runtime_stop() -> dict[str, object]:
    result = _utm_runtime_manager().stop()
    await controller.emit_workspace_result(
        workspace="equipment",
        tool="equipment.utm_runtime.stop",
        result=result,
        stage=Stage.EQUIPMENT,
        module_id="equipment",
        agent="equipment_agent",
        workflow="utm_vision_runtime",
        node_event=True,
    )
    return result
```

- [x] **Step 4: Add config**

In `configs/devices.yaml`, add:

```yaml
devices:
  utm_vision_runtime:
    enabled: true
    workspace_root: /home/lee-junyoung/yolo_ros_ws/UTM_VISION
    script_path: /home/lee-junyoung/yolo_ros_ws/UTM_VISION/scripts/start_utm_vision_stack.sh
    log_dir: artifacts/utm_runtime
    stop_timeout_sec: 5.0
```

- [x] **Step 5: Verify endpoint tests**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/integration/test_utm_runtime_gui_api.py -q
```

Expected green result:

```text
2 passed
```

## Task 3: Add the Main GUI Loading Control

**Files:**
- Modify: `web/templates/index.html`
- Modify: `web/static/app.js`
- Test: `tests/integration/test_utm_runtime_gui_api.py`

- [x] **Step 1: Add failing GUI assertions**

The integration test must assert the main page contains:

```text
UTM Vision Runtime
camera_rect · green_dot_monitor · YOLO
utm-runtime-workspace-dot
utm-runtime-workspace-detail
btn-utm-runtime-load
btn-utm-runtime-stop
```

It must also assert `/static/app.js` contains:

```text
/api/equipment/utm-runtime/status
/api/equipment/utm-runtime/start
/api/equipment/utm-runtime/stop
refreshUtmRuntimeStatus
startUtmRuntime
utmRuntimeStatusTimer
```

- [x] **Step 2: Add GUI card**

In `web/templates/index.html`, add this workspace card:

```html
<article class="workspace-card">
  <div class="status-head">
    <span class="status-title">UTM Vision Runtime</span>
    <span id="utm-runtime-workspace-dot" class="status-dot idle"></span>
  </div>
  <strong>camera_rect · green_dot_monitor · YOLO</strong>
  <p id="utm-runtime-workspace-detail">Reading UTM Vision runtime status.</p>
  <div class="button-row compact-tools">
    <button id="btn-utm-runtime-load" class="btn primary" type="button">Loading</button>
    <button id="btn-utm-runtime-stop" class="btn danger" type="button">Stop</button>
  </div>
</article>
```

- [x] **Step 3: Add JavaScript DOM handles**

In `web/static/app.js`, add:

```javascript
const utmRuntimeWorkspaceDotEl = document.getElementById("utm-runtime-workspace-dot");
const utmRuntimeWorkspaceDetailEl = document.getElementById("utm-runtime-workspace-detail");
const btnUtmRuntimeLoad = document.getElementById("btn-utm-runtime-load");
const btnUtmRuntimeStop = document.getElementById("btn-utm-runtime-stop");
let utmRuntimeStatusTimer = null;
```

- [x] **Step 4: Add status rendering and API calls**

Add:

```javascript
async function refreshUtmRuntimeStatus() {
  const res = await fetch("/api/equipment/utm-runtime/status");
  const data = await res.json();
  renderUtmRuntimeStatus(data);
}

async function startUtmRuntime() {
  btnUtmRuntimeLoad.disabled = true;
  btnUtmRuntimeLoad.textContent = "Loading...";
  try {
    const data = await postJson("/api/equipment/utm-runtime/start", {});
    renderUtmRuntimeStatus(data);
    await refreshState();
  } finally {
    await refreshUtmRuntimeStatus();
  }
}

async function stopUtmRuntime() {
  btnUtmRuntimeStop.disabled = true;
  btnUtmRuntimeStop.textContent = "Stopping...";
  try {
    const data = await postJson("/api/equipment/utm-runtime/stop", {});
    renderUtmRuntimeStatus(data);
    await refreshState();
  } finally {
    btnUtmRuntimeStop.textContent = "Stop";
    await refreshUtmRuntimeStatus();
  }
}
```

- [x] **Step 5: Add polling**

In `bootstrap()`, add:

```javascript
await refreshUtmRuntimeStatus();
if (!utmRuntimeStatusTimer) {
  utmRuntimeStatusTimer = window.setInterval(refreshUtmRuntimeStatus, 5000);
}
```

- [x] **Step 6: Bump the JS cache key**

In `web/templates/index.html`, set:

```html
<script src="/static/app.js?v=20260619-utm-runtime-2" defer></script>
```

- [x] **Step 7: Verify GUI tests**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/integration/test_utm_runtime_gui_api.py -q
```

Expected green result:

```text
2 passed
```

## Task 4: Add the ROS Stack Script

**Files:**
- Create: `/home/lee-junyoung/yolo_ros_ws/UTM_VISION/scripts/start_utm_vision_stack.sh`
- Modify: `/home/lee-junyoung/yolo_ros_ws/UTM_VISION/README.md`
- Test: `tests/unit/test_utm_runtime_stack_script.py`

- [x] **Step 1: Write script regression tests**

Create `tests/unit/test_utm_runtime_stack_script.py` and assert the script:

```text
disables nounset before source "$setup_path"
reenables nounset after source "$setup_path"
sets YOLO_MODEL_PATH
passes model:="$YOLO_MODEL_PATH" to yolo_bringup
```

Expected red result before fixes:

```text
assert "set +u" in script
assert "YOLO_MODEL_PATH=" in script
```

- [x] **Step 2: Create the stack script**

Create `/home/lee-junyoung/yolo_ros_ws/UTM_VISION/scripts/start_utm_vision_stack.sh` with:

```bash
#!/usr/bin/env bash
set -euo pipefail

source_if_exists() {
  local setup_path="$1"
  if [[ -f "$setup_path" ]]; then
    set +u
    source "$setup_path"
    set -u
  fi
}

source_if_exists /opt/ros/lyrical/setup.bash
source_if_exists "$HOME/image_pipeline_ws/install/setup.bash"
source_if_exists "$HOME/usb_cam_ws/install/setup.bash"
source_if_exists "$HOME/yolo_ros_ws/install/setup.bash"
source_if_exists "$HOME/yolo_ros_ws/UTM_VISION/install/setup.bash"

UTM_VISION_ROOT="${UTM_VISION_ROOT:-$HOME/yolo_ros_ws/UTM_VISION}"
YOLO_MODEL_PATH="${YOLO_MODEL_PATH:-/home/lee-junyoung/yolo_ros_ws/yolov8m.pt}"
CAMERA_STARTUP_DELAY_SEC="${UTM_CAMERA_STARTUP_DELAY_SEC:-2}"
MONITOR_STARTUP_DELAY_SEC="${UTM_MONITOR_STARTUP_DELAY_SEC:-1}"
```

Start the three ROS launch processes:

```bash
start_camera_rect &
ros2 launch compression_tester_monitor green_dot_monitor.launch.py \
  input_image_topic:=/camera/image_rect \
  output_image_topic:=/image_utm \
  working_height_threshold_px:=250.0 \
  use_roi:=True \
  roi_x_min:=180 roi_x_max:=410 \
  roi_y_min:=0 roi_y_max:=0 \
  hide_outside_roi:=False &
ros2 launch yolo_bringup yolov8.launch.py \
  model:="$YOLO_MODEL_PATH" \
  input_image_topic:=/image_utm \
  classes:=0 \
  threshold:=0.7 &
```

Use a trap to terminate all child PIDs on `INT`, `TERM`, or process exit.

- [x] **Step 3: Make script executable**

Run:

```bash
chmod +x /home/lee-junyoung/yolo_ros_ws/UTM_VISION/scripts/start_utm_vision_stack.sh
```

- [x] **Step 4: Document script usage**

In `/home/lee-junyoung/yolo_ros_ws/UTM_VISION/README.md`, add:

```bash
~/yolo_ros_ws/UTM_VISION/scripts/start_utm_vision_stack.sh
```

Explain that the `autonomous_researcher` GUI calls this script through the `UTM Vision Runtime` Loading button.

- [x] **Step 5: Verify script tests and syntax**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/unit/test_utm_runtime_stack_script.py -q
bash -n /home/lee-junyoung/yolo_ros_ws/UTM_VISION/scripts/start_utm_vision_stack.sh
```

Expected result:

```text
2 passed
```

`bash -n` should exit with status `0`.

## Task 5: Live Debugging Fixes Already Applied

**Files:**
- Modify: `/home/lee-junyoung/yolo_ros_ws/UTM_VISION/scripts/start_utm_vision_stack.sh`
- Modify: `web/static/app.js`
- Modify: `web/templates/index.html`
- Test: `tests/unit/test_utm_runtime_stack_script.py`
- Test: `tests/integration/test_utm_runtime_gui_api.py`

- [x] **Step 1: Fix ROS setup sourcing under `set -u`**

Observed failure:

```text
/opt/ros/lyrical/setup.bash: line 8: AMENT_TRACE_SETUP_FILES: unbound variable
```

Root cause:

```text
start_utm_vision_stack.sh used set -u while sourcing ROS setup files.
```

Fix:

```bash
set +u
source "$setup_path"
set -u
```

- [x] **Step 2: Fix YOLO model path**

Observed behavior:

```text
yolo_node logged "Activating..." but did not reach "Activated" when the GUI-launched script used the UTM_VISION directory as cwd.
```

Root cause:

```text
yolov8.launch.py defaulted to relative model path yolov8m.pt.
The GUI subprocess cwd is /home/lee-junyoung/yolo_ros_ws/UTM_VISION.
The model file is available at /home/lee-junyoung/yolo_ros_ws/yolov8m.pt.
```

Fix:

```bash
YOLO_MODEL_PATH="${YOLO_MODEL_PATH:-/home/lee-junyoung/yolo_ros_ws/yolov8m.pt}"
ros2 launch yolo_bringup yolov8.launch.py \
  model:="$YOLO_MODEL_PATH" \
  input_image_topic:=/image_utm \
  classes:=0 \
  threshold:=0.7
```

- [x] **Step 3: Add UTM runtime polling to the GUI**

Observed behavior:

```text
The backend status changed after manual retest, but an already-open browser needed a refresh to see the new runtime status.
```

Fix:

```javascript
let utmRuntimeStatusTimer = null;

if (!utmRuntimeStatusTimer) {
  utmRuntimeStatusTimer = window.setInterval(refreshUtmRuntimeStatus, 5000);
}
```

## Task 6: Verification Commands

**Files:**
- Test: `tests/unit/test_utm_runtime_bridge.py`
- Test: `tests/unit/test_utm_runtime_stack_script.py`
- Test: `tests/integration/test_utm_runtime_gui_api.py`

- [x] **Step 1: Run focused automated tests**

Run:

```bash
cd /home/lee-junyoung/autonomous_researcher
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest \
  tests/unit/test_utm_runtime_bridge.py \
  tests/unit/test_utm_runtime_stack_script.py \
  tests/integration/test_utm_runtime_gui_api.py \
  -q
```

Verified result:

```text
6 passed
```

- [x] **Step 2: Run Python and shell syntax checks**

Run:

```bash
cd /home/lee-junyoung/autonomous_researcher
python -m py_compile device_bridges/utm_runtime_bridge.py app/main.py
bash -n /home/lee-junyoung/yolo_ros_ws/UTM_VISION/scripts/start_utm_vision_stack.sh
```

Verified result:

```text
exit status 0
```

- [x] **Step 3: Verify FastAPI page and runtime API**

Run:

```bash
python - <<'PY'
import json, urllib.request
status = json.loads(urllib.request.urlopen("http://127.0.0.1:7860/api/equipment/utm-runtime/status", timeout=3).read().decode("utf-8"))
print(status.get("ok"), status.get("status"), status.get("pid"))
html = urllib.request.urlopen("http://127.0.0.1:7860/", timeout=3).read().decode("utf-8")
print("page_has_utm", "UTM Vision Runtime" in html, "20260619-utm-runtime-2" in html)
PY
```

Verified result:

```text
True running 146917
page_has_utm True True
```

- [x] **Step 4: Verify ROS output topics**

Run:

```bash
source /opt/ros/lyrical/setup.bash
source /home/lee-junyoung/usb_cam_ws/install/setup.bash
source /home/lee-junyoung/image_pipeline_ws/install/setup.bash
source /home/lee-junyoung/yolo_ros_ws/install/setup.bash
source /home/lee-junyoung/yolo_ros_ws/UTM_VISION/install/setup.bash
ros2 topic list | rg '/camera/image_rect|/image_utm|/compression_tester/summary|/yolo/dbg_image|/yolo/detections'
```

Verified topics:

```text
/camera/image_rect
/compression_tester/summary
/image_utm
/yolo/dbg_image
/yolo/detections
```

- [x] **Step 5: Verify `/image_utm` rate**

Run:

```bash
timeout 6 ros2 topic hz /image_utm
```

Verified result:

```text
average rate: about 29.5 Hz
```

- [x] **Step 6: Verify YOLO activation**

Run:

```bash
rg -n 'yolo_node.*Activated' /home/lee-junyoung/autonomous_researcher/artifacts/utm_runtime/utm_runtime_20260619T082009Z.log
```

Verified result:

```text
[yolo_node-1] ... [yolo_node] Activated
```

## Task 7: Add Time-Windowed UTM State Observation

**Files to modify when this phase starts:**
- Create: `device_bridges/utm_state_observer.py`
- Modify: `app/main.py`
- Modify: `mcp_tools/camera_tools.py`
- Modify: `app/bootstrap.py`
- Create: `tests/unit/test_utm_state_observer.py`
- Create: `tests/unit/test_camera_tools_utm_runtime.py`
- Modify: `tests/unit/test_equipment_agent.py`
- Modify: `docs/hardware/utm_vision_runtime_gui.md`

- [ ] **Step 1: Define observation contract**

The UTM state observer must collect multiple samples over a time window. Default values:

```text
duration_sec: 5.0
sample_interval_sec: 0.2
minimum_samples: 8
freshness_max_age_sec: 1.0
```

Each sample must include:

```json
{
  "timestamp": "2026-06-19T17:20:00.000000+09:00",
  "state": "WORKING",
  "span_y": 248.2,
  "marker_count": 2,
  "upper_marker_detected": true,
  "lower_marker_detected": true,
  "summary_fresh": true
}
```

The aggregate response must include:

```json
{
  "ok": true,
  "duration_sec": 5.0,
  "sample_count": 25,
  "working_count": 18,
  "not_working_count": 7,
  "unknown_count": 0,
  "initial_state": "NOT_WORKING",
  "final_state": "WORKING",
  "transition": "NOT_WORKING_TO_WORKING",
  "stable_state": "",
  "samples": []
}
```

- [ ] **Step 2: Define state-sequence rules**

Use these rules for equipment cross-checks:

```text
utm_pre_start:
  pass when the stack is running, summaries are fresh, and at least 80% of samples detect both upper and lower markers.

utm_motion_confirm:
  pass when the observation window contains NOT_WORKING_TO_WORKING, WORKING_TO_NOT_WORKING, or meaningful span_y movement.

utm_test_complete:
  pass only when UTM software/export evidence is available and the vision sequence is not UNKNOWN-dominated.
```

State transition detection:

```text
NOT_WORKING_TO_WORKING:
  initial stable segment contains NOT_WORKING
  final stable segment contains WORKING
  both segments have at least 3 valid samples

STABLE_WORKING:
  at least 80% valid samples are WORKING

STABLE_NOT_WORKING:
  at least 80% valid samples are NOT_WORKING

UNSTABLE:
  valid samples exist but no stable state or transition dominates

INSUFFICIENT_EVIDENCE:
  fewer than minimum_samples or marker detection is not reliable
```

- [ ] **Step 3: Write failing observer tests**

Create `tests/unit/test_utm_state_observer.py` with deterministic sample lists:

```python
def test_observer_detects_not_working_to_working_transition():
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
```

Also add:

```python
def test_observer_fails_closed_for_single_sample():
    result = summarize_utm_state_sequence(
        [{"state": "WORKING", "span_y": 240.0, "marker_count": 2}],
        minimum_samples=6,
    )

    assert result["ok"] is False
    assert result["failure_code"] == "UTM_INSUFFICIENT_TEMPORAL_EVIDENCE"
```

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/unit/test_utm_state_observer.py -q
```

Expected red result before implementation:

```text
ModuleNotFoundError: No module named 'device_bridges.utm_state_observer'
```

- [ ] **Step 4: Implement pure sequence summarizer**

Create `device_bridges/utm_state_observer.py` with a pure function first:

```python
from __future__ import annotations

from collections import Counter
from typing import Any


VALID_STATES = {"WORKING", "NOT_WORKING"}
INSUFFICIENT_EVIDENCE = "UTM_INSUFFICIENT_TEMPORAL_EVIDENCE"


def _sample_state(sample: dict[str, Any]) -> str:
    return str(sample.get("state", "UNKNOWN")).upper()


def _sample_marker_count(sample: dict[str, Any]) -> int:
    value = sample.get("point_count", sample.get("marker_count", 0))
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _valid_samples(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        sample
        for sample in samples
        if _sample_state(sample) in VALID_STATES and _sample_marker_count(sample) >= 2
    ]


def summarize_utm_state_sequence(
    samples: list[dict[str, Any]],
    *,
    minimum_samples: int = 8,
    stable_ratio: float = 0.8,
) -> dict[str, Any]:
    valid = _valid_samples(samples)
    if len(valid) < minimum_samples:
        return {
            "ok": False,
            "failure_code": INSUFFICIENT_EVIDENCE,
            "sample_count": len(samples),
            "valid_sample_count": len(valid),
            "working_count": 0,
            "not_working_count": 0,
            "unknown_count": len(samples) - len(valid),
            "transition": "INSUFFICIENT_EVIDENCE",
            "stable_state": "",
        }

    states = [_sample_state(sample) for sample in valid]
    counts = Counter(states)
    working_count = counts["WORKING"]
    not_working_count = counts["NOT_WORKING"]
    threshold = max(1, int(round(len(valid) * stable_ratio)))

    first_segment = states[:3]
    last_segment = states[-3:]
    transition = "UNSTABLE"
    stable_state = ""
    if first_segment.count("NOT_WORKING") >= 2 and last_segment.count("WORKING") >= 2:
        transition = "NOT_WORKING_TO_WORKING"
    elif first_segment.count("WORKING") >= 2 and last_segment.count("NOT_WORKING") >= 2:
        transition = "WORKING_TO_NOT_WORKING"
    elif working_count >= threshold:
        transition = "STABLE_WORKING"
        stable_state = "WORKING"
    elif not_working_count >= threshold:
        transition = "STABLE_NOT_WORKING"
        stable_state = "NOT_WORKING"

    span_values = [
        float(sample["span_y"])
        for sample in valid
        if isinstance(sample.get("span_y"), (int, float))
    ]
    span_y_delta = max(span_values) - min(span_values) if span_values else 0.0

    return {
        "ok": True,
        "sample_count": len(samples),
        "valid_sample_count": len(valid),
        "working_count": working_count,
        "not_working_count": not_working_count,
        "unknown_count": len(samples) - len(valid),
        "initial_state": states[0],
        "final_state": states[-1],
        "transition": transition,
        "stable_state": stable_state,
        "span_y_delta": span_y_delta,
        "samples": samples,
    }
```

This function must not import ROS. It only summarizes dictionaries so unit tests stay deterministic.

- [ ] **Step 5: Add live sample collection after summarizer tests pass**

Add a collector function that runs outside ROS imports by shelling out to a helper or by reading a JSON-producing subprocess:

```python
import json
import subprocess
import time
from collections.abc import Callable
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_ros2_string_data(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if text.startswith("data:"):
        text = text.split(":", 1)[1].strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        text = text[1:-1]
    payload = json.loads(text)
    payload["timestamp"] = _now_iso()
    payload["summary_fresh"] = True
    payload["upper_marker_detected"] = _sample_marker_count(payload) >= 2
    payload["lower_marker_detected"] = _sample_marker_count(payload) >= 2
    return payload


def read_compression_tester_summary_once(
    *,
    topic: str = "/compression_tester/summary",
    timeout_sec: float = 1.0,
) -> dict[str, Any]:
    completed = subprocess.run(
        ["ros2", "topic", "echo", topic, "--once", "--field", "data"],
        capture_output=True,
        check=True,
        text=True,
        timeout=timeout_sec + 0.5,
    )
    return _parse_ros2_string_data(completed.stdout)


def observe_utm_state_window(
    *,
    duration_sec: float = 5.0,
    sample_interval_sec: float = 0.2,
    minimum_samples: int = 8,
    read_sample: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    reader = read_sample or read_compression_tester_summary_once
    deadline = time.monotonic() + duration_sec
    samples: list[dict[str, Any]] = []

    while time.monotonic() < deadline:
        try:
            samples.append(reader())
        except (
            json.JSONDecodeError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
        ) as exc:
            samples.append(
                {
                    "timestamp": _now_iso(),
                    "state": "UNKNOWN",
                    "point_count": 0,
                    "summary_fresh": False,
                    "error": type(exc).__name__,
                }
            )
        time.sleep(sample_interval_sec)

    result = summarize_utm_state_sequence(samples, minimum_samples=minimum_samples)
    result["duration_sec"] = duration_sec
    return result
```

The collector must call `summarize_utm_state_sequence()` and return fail-closed payloads when the runtime is stopped or samples are stale.

## Task 8: Register Agent Function-Calling Monitoring Path

**Files to modify when this phase starts:**
- `mcp_tools/camera_tools.py`
- `app/bootstrap.py`
- `device_bridges/utm_state_observer.py`
- `tests/unit/test_camera_tools_utm_runtime.py`
- `tests/unit/test_equipment_agent.py`

- [ ] **Step 1: Add tests for the agent function-call contract**

Create `tests/unit/test_camera_tools_utm_runtime.py` with:

```python
from mcp_tools.camera_tools import register_camera_tools
from mcp_tools.tool_registry import ToolRegistry


def test_agent_monitoring_call_observes_utm_window():
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
    assert result["results"][0]["check_id"] == "utm_motion_confirm"
    assert result["results"][0]["evidence"]["transition"] == "NOT_WORKING_TO_WORKING"
```

Add:

```python
def test_agent_monitoring_call_rejects_single_sample_observation():
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
```

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/unit/test_camera_tools_utm_runtime.py -q
```

Expected red result before implementation:

```text
TypeError: register_camera_tools() got an unexpected keyword argument 'utm_state_observer'
```

- [ ] **Step 2: Implement the live UTM route in `vision.equipment_cross_check`**

Change `mcp_tools/camera_tools.py` so `register_camera_tools()` accepts an optional observer:

```python
from collections.abc import Callable


UTM_CHECK_IDS = {"utm_pre_start", "utm_motion_confirm", "utm_test_complete"}
UtmStateObserver = Callable[..., dict[str, Any]]


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
        "check_id": check_id,
        "ok": False,
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
        "check_id": check_id,
        "ok": True,
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
        },
        "source": "utm_vision",
    }


def _map_utm_observation_to_cross_check(check_id: str, observation: dict[str, Any]) -> dict[str, Any]:
    if not observation.get("ok"):
        return _utm_failure_result(check_id, observation)
    return _utm_success_result(check_id, observation)
```

Move the current simulator body of `_equipment_cross_check(payload)` into `_simulated_equipment_cross_check(payload)`, then make `_equipment_cross_check()` route live UTM checks:

```python
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

    utm_checks = [item for item in checks if isinstance(item, dict) and item.get("check_id") and _is_utm_check(item)]
    if mode == "live" and utm_state_observer is not None and utm_checks:
        results = []
        for item in utm_checks:
            observation = utm_state_observer(
                duration_sec=duration_sec,
                sample_interval_sec=sample_interval_sec,
                minimum_samples=minimum_samples,
            )
            results.append(_map_utm_observation_to_cross_check(str(item["check_id"]), observation))
        ok = bool(results) and all(item.get("ok") for item in results)
        return {
            "ok": ok,
            "tool": "vision.equipment_cross_check",
            "runtime_mode": mode,
            "results": results,
            "failure_code": None if ok else results[0].get("failure_code"),
        }

    return _simulated_equipment_cross_check(payload)
```

Register the tool with a closure:

```python
def register_camera_tools(
    registry: ToolRegistry,
    *,
    utm_state_observer: UtmStateObserver | None = None,
) -> None:
    registry.register("camera.capture", _camera_capture)
    registry.register(
        "vision.equipment_cross_check",
        lambda payload: _equipment_cross_check(payload, utm_state_observer=utm_state_observer),
    )
```

- [ ] **Step 3: Wire the observer in bootstrap**

Change `app/bootstrap.py` registration from:

```python
register_camera_tools(tools)
```

to:

```python
from device_bridges.utm_state_observer import observe_utm_state_window

utm_runtime_enabled = bool(cfg.get("devices", {}).get("utm_vision_runtime", {}).get("enabled"))
register_camera_tools(
    tools,
    utm_state_observer=observe_utm_state_window if utm_runtime_enabled else None,
)
```

- [ ] **Step 4: Verify successful function-call return shape**

The successful `vision.equipment_cross_check` return must look like:

```json
{
  "ok": true,
  "tool": "vision.equipment_cross_check",
  "runtime_mode": "live",
  "results": [
    {
      "check_id": "utm_motion_confirm",
      "ok": true,
      "status": "verified",
      "message": "UTM vision observed NOT_WORKING_TO_WORKING over 5.0s",
      "evidence": {
        "duration_sec": 5.0,
        "sample_count": 25,
        "transition": "NOT_WORKING_TO_WORKING",
        "initial_state": "NOT_WORKING",
        "final_state": "WORKING"
      },
      "source": "utm_vision"
    }
  ],
  "failure_code": null
}
```

- [ ] **Step 5: Verify fail-closed function-call return shape**

The insufficient-evidence return must look like:

```json
{
  "ok": false,
  "tool": "vision.equipment_cross_check",
  "runtime_mode": "live",
  "results": [
    {
      "check_id": "utm_motion_confirm",
      "ok": false,
      "status": "blocked",
      "failure_code": "UTM_INSUFFICIENT_TEMPORAL_EVIDENCE",
      "message": "UTM vision requires a time-windowed observation; one sample is not enough.",
      "source": "utm_vision"
    }
  ],
  "failure_code": "UTM_INSUFFICIENT_TEMPORAL_EVIDENCE"
}
```

- [ ] **Step 6: Keep simulator behavior unchanged**

When `devices.utm_vision_runtime.enabled` is false, when `runtime_mode` is not `live`, or when a check is not a UTM check, existing deterministic `camera.capture` and mock `vision.equipment_cross_check` behavior must continue for non-UTM workflows.

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/unit/test_camera_tools_utm_runtime.py tests/unit/test_vision_agent.py -q
```

Expected green result after implementation:

```text
all selected tests pass
```

## Operating Procedure

Start the GUI server:

```bash
cd /home/lee-junyoung/autonomous_researcher
AUTONOMOUS_RELOAD=0 AUTONOMOUS_PORT=7860 python -m app.serve
```

Open:

```text
http://127.0.0.1:7860
```

Click:

```text
Device Workspaces -> UTM Vision Runtime -> Loading
```

Check status:

```bash
curl http://127.0.0.1:7860/api/equipment/utm-runtime/status
```

Stop the stack:

```text
Device Workspaces -> UTM Vision Runtime -> Stop
```

Logs:

```text
/home/lee-junyoung/autonomous_researcher/artifacts/utm_runtime/
```

## Self-Review

- Spec coverage: This updated plan covers the actual GUI Loading button flow, FastAPI runtime-control API, subprocess manager, ROS stack script, live debugging fixes, verification commands, the required future time-windowed UTM state observer, and the agent function-calling monitoring path.
- Placeholder scan: No unresolved placeholder markers or unspecified implementation steps remain. Remaining literal ellipses are UI labels, log excerpts, `subprocess.Popen(..., start_new_session=True)`, or Python `Callable[..., dict[str, Any]]` type syntax.
- Type consistency: Endpoint names, button IDs, file paths, test names, config keys, and observation fields match the current implementation direction.
