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
