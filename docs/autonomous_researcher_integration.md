# Autonomous Researcher Integration

This document explains how the UTM ROS vision package is connected to the
`autonomous_researcher` agent runtime and GUI.

## Directory Layout

The integration files copied from the agent project are stored in:

```text
autonomous_researcher_required_files/
```

Important files:

```text
autonomous_researcher_required_files/
  app/bootstrap.py
  device_bridges/utm_runtime_bridge.py
  device_bridges/utm_state_observer.py
  mcp_tools/camera_tools.py
  web/templates/index.html
  web/static/app.js
  configs/devices.yaml
  docs/hardware/utm_vision_runtime_gui.md
  docs/superpowers/plans/2026-06-19-utm-vision-api-integration.md
  tests/unit/test_utm_runtime_bridge.py
  tests/unit/test_utm_runtime_stack_script.py
  tests/unit/test_utm_state_observer.py
  tests/unit/test_camera_tools_utm_runtime.py
  tests/integration/test_utm_runtime_gui_api.py
```

Apply them by copying each file to the same relative path inside an
`autonomous_researcher` checkout.

## Runtime Start/Stop

The GUI does not start each ROS process manually. It calls a small FastAPI
runtime-control API:

```text
GET  /api/equipment/utm-runtime/status
POST /api/equipment/utm-runtime/start
POST /api/equipment/utm-runtime/stop
```

The start endpoint launches:

```bash
~/yolo_ros_ws/UTM_VISION/scripts/start_utm_vision_stack.sh
```

That script starts the stack as one process group:

```text
camera_rect
green_dot_monitor
yolo
```

The stop endpoint terminates the process group, so the camera, green-dot
monitor, and YOLO process stop together.

## Agent Function-Calling Flow

Natural-language monitoring is expected to flow through the agent tool registry:

```text
User: "UTM 모니터링해"
  -> Equipment/Vision agent chooses a tool call
  -> ToolRegistry.call("vision.equipment_cross_check", payload)
  -> mcp_tools.camera_tools._equipment_cross_check(payload)
  -> device_bridges.utm_state_observer.observe_utm_state_window(...)
  -> repeated reads from /compression_tester/summary
  -> structured JSON result returned to the agent
```

The monitoring function samples for a time window. It never treats a single
image frame as enough evidence.

Default observation values:

```text
duration_sec: 5.0
sample_interval_sec: 0.2
minimum_samples: 8
```

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

Example success response:

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

If the function receives too few valid samples, it fails closed:

```json
{
  "ok": false,
  "failure_code": "UTM_INSUFFICIENT_TEMPORAL_EVIDENCE"
}
```

## Check Gates

The live UTM checks are stricter than a generic boolean result:

```text
utm_pre_start
  Requires fresh summaries and reliable upper/lower marker detection.

utm_motion_confirm
  Requires NOT_WORKING_TO_WORKING, WORKING_TO_NOT_WORKING, or meaningful span_y movement.

utm_test_complete
  Requires non-UNKNOWN-dominated vision evidence plus UTM software/export evidence.
```

## ROS Topics

The observer reads:

```text
/compression_tester/summary
```

The current green-dot monitor publishes that topic as `std_msgs/String`
containing JSON fields such as:

```json
{
  "state": "WORKING",
  "span_y": 248.2,
  "point_count": 2,
  "raw_point_count": 3,
  "selected_point_count": 2,
  "tracking_hold": false,
  "points": []
}
```

Other useful topics:

```text
/camera/image_rect
/image_utm
/compression_tester/state
/compression_tester/metrics
/compression_tester/green_points
/yolo/dbg_image
/yolo/detections
```

## Operator Procedure

1. Confirm the BRIO camera is connected directly to a stable USB port.
2. Start the agent GUI server:

   ```bash
   cd ~/github_utm_integration/autonomous_researcher
   AUTONOMOUS_RELOAD=0 AUTONOMOUS_PORT=7860 python -m app.serve
   ```

3. Open:

   ```text
   http://127.0.0.1:7860
   ```

4. Press:

   ```text
   Device Workspaces -> UTM Vision Runtime -> Loading
   ```

5. Check ROS outputs:

   ```bash
   ros2 topic hz /image_utm
   ros2 topic echo /compression_tester/summary --once
   ros2 topic echo /yolo/detections --once
   ```

6. Ask the agent to monitor the UTM state. The expected implementation path is
   the `vision.equipment_cross_check` function call described above.

## Verification Commands

Run from the autonomous researcher checkout:

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

The current environment has ROS pytest plugins that can conflict with plain
pytest auto-loading. `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` keeps these focused
unit/integration checks isolated from ROS launch-testing plugins.

## Screenshots

Suggested screenshots to capture for future documentation:

```text
docs/assets/utm-runtime-card.png
docs/assets/image-utm-rqt.png
docs/assets/compression-summary-topic.png
docs/assets/yolo-debug-image.png
```

Recommended views:

- The `UTM Vision Runtime` GUI card after pressing `Loading`.
- `rqt_image_view` on `/image_utm`.
- Terminal output from `ros2 topic echo /compression_tester/summary --once`.
- YOLO debug output from `/yolo/dbg_image`.
