# UTM Vision Runtime GUI

The main GUI has a `UTM Vision Runtime` workspace card. Pressing `Loading`
starts the local ROS 2 UTM vision stack through:

```bash
/home/lee-junyoung/yolo_ros_ws/UTM_VISION/scripts/start_utm_vision_stack.sh
```

That script launches:

```text
camera_rect
green_dot_monitor
yolo
```

## API

```text
GET  /api/equipment/utm-runtime/status
POST /api/equipment/utm-runtime/start
POST /api/equipment/utm-runtime/stop
```

The server keeps the stack as one process group. If `Stop` is pressed, the full
camera/UTM/YOLO stack is terminated together.

## Runtime Architecture

The GUI and API only own process lifecycle. ROS nodes remain outside the Python
web runtime:

```text
web/static/app.js
  -> POST /api/equipment/utm-runtime/start
  -> app/main.py endpoint
  -> UTMRuntimeProcessManager
  -> /home/lee-junyoung/yolo_ros_ws/UTM_VISION/scripts/start_utm_vision_stack.sh
  -> camera_rect + green_dot_monitor + yolo
```

The stack script publishes these topics when healthy:

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

## Configuration

The default paths are in `configs/devices.yaml`:

```yaml
devices:
  utm_vision_runtime:
    workspace_root: /home/lee-junyoung/yolo_ros_ws/UTM_VISION
    script_path: /home/lee-junyoung/yolo_ros_ws/UTM_VISION/scripts/start_utm_vision_stack.sh
    log_dir: artifacts/utm_runtime
```

Logs are written under `artifacts/utm_runtime`.

## Agent Monitoring Function Call

The runtime API only starts and stops the ROS stack. UTM working state is judged
through the agent-callable `vision.equipment_cross_check` tool, not from a
single image sample.

Example payload:

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

The tool calls `observe_utm_state_window()`, samples
`/compression_tester/summary` repeatedly for the requested time window, and
returns transition evidence such as `NOT_WORKING_TO_WORKING`,
`STABLE_WORKING`, or `STABLE_NOT_WORKING`.

Function-call path:

```text
User input: "UTM 모니터링해"
  -> agent selects vision.equipment_cross_check
  -> ToolRegistry.call("vision.equipment_cross_check", payload)
  -> mcp_tools.camera_tools._equipment_cross_check(...)
  -> device_bridges.utm_state_observer.observe_utm_state_window(...)
  -> repeated ros2 topic echo /compression_tester/summary --once --field data
  -> JSON result returned to the agent
```

Check-specific gates:

```text
utm_pre_start      requires reliable upper/lower marker detection
utm_motion_confirm requires a state transition or meaningful span_y movement
utm_test_complete  requires non-UNKNOWN-dominated vision plus UTM/export evidence
```

If only one sample or too few valid samples are available, the tool fails closed
with:

```text
UTM_INSUFFICIENT_TEMPORAL_EVIDENCE
```

Example success result:

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

## Operator Procedure

1. Start the GUI server:

   ```bash
   cd /home/lee-junyoung/github_utm_integration/autonomous_researcher
   AUTONOMOUS_RELOAD=0 AUTONOMOUS_PORT=7860 python -m app.serve
   ```

2. Open:

   ```text
   http://127.0.0.1:7860
   ```

3. Click:

   ```text
   Device Workspaces -> UTM Vision Runtime -> Loading
   ```

4. Check API state:

   ```bash
   curl http://127.0.0.1:7860/api/equipment/utm-runtime/status
   ```

5. Confirm ROS outputs:

   ```bash
   ros2 topic hz /image_utm
   ros2 topic echo /compression_tester/summary --once --field data
   ```

6. Ask the agent to monitor the UTM state. The expected tool path is
   `vision.equipment_cross_check`.

## Verification

Focused tests:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest \
  tests/unit/test_utm_state_observer.py \
  tests/unit/test_camera_tools_utm_runtime.py \
  tests/unit/test_utm_runtime_bridge.py \
  tests/unit/test_utm_runtime_stack_script.py \
  tests/integration/test_utm_runtime_gui_api.py \
  -q
```

Compile check:

```bash
python -m py_compile \
  device_bridges/utm_state_observer.py \
  mcp_tools/camera_tools.py \
  app/bootstrap.py \
  app/main.py
```

The ROS installation can auto-load pytest plugins such as `launch_testing`.
Use `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` for these focused non-ROS unit tests.

## Suggested Screenshots

Useful screenshots for future reports:

```text
docs/assets/readme/utm-runtime-card.png
docs/assets/readme/utm-image-rqt.png
docs/assets/readme/utm-summary-topic.png
docs/assets/readme/utm-yolo-debug.png
```

Capture targets:

- GUI `UTM Vision Runtime` card after `Loading`.
- `rqt_image_view` on `/image_utm`.
- Terminal output from `/compression_tester/summary`.
- YOLO debug image on `/yolo/dbg_image`.
