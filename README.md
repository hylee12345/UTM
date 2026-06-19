# UTM_VISION

Fixed-camera ROS 2 vision workflow for monitoring a compression tester with green visual markers and feeding an annotated image into YOLO.

## Overview

The system is split into three runtime steps:

```text
camera_rect
  publishes /camera/image_raw and /camera/image_rect
  defaults to 640x480 YUYV input converted to RGB

green_dot_monitoring
  subscribes /camera/image_rect
  detects green marker dots
  publishes /image_utm and /compression_tester/*

yolo
  subscribes /image_utm
  publishes /yolo/detections, /yolo/tracking, /yolo/dbg_image
```

The green-dot monitor computes marker coordinates and classifies the compression tester state:

```text
span_y = y_max - y_min
span_y <= 250 px -> WORKING
span_y > 250 px  -> NOT_WORKING
```

`/image_utm` draws the compression tester marker bounding box:

```text
WORKING     -> red bounding box
NOT_WORKING -> blue bounding box
UNKNOWN     -> yellow overlay
```

## Autonomous Researcher Integration

This repository now also carries the files needed to connect the UTM vision
pipeline to the `autonomous_researcher` agent runtime. The integration keeps ROS
execution outside the FastAPI web process:

```text
GUI Loading button
  -> POST /api/equipment/utm-runtime/start
  -> UTMRuntimeProcessManager
  -> scripts/start_utm_vision_stack.sh
  -> camera_rect + green_dot_monitor + yolo
```

Monitoring is separate from start/stop. When an agent receives a request such as
`UTM 모니터링해`, it should call `vision.equipment_cross_check`. That function
samples `/compression_tester/summary` repeatedly for several seconds and returns
a structured JSON result. It does not decide from one image frame.

```text
ToolRegistry.call("vision.equipment_cross_check", payload)
  -> observe_utm_state_window(duration_sec=5.0, sample_interval_sec=0.2, minimum_samples=8)
  -> summarize_utm_state_sequence(samples)
  -> return WORKING / NOT_WORKING / transition evidence
```

The autonomous researcher files are stored under:

```text
autonomous_researcher_required_files/
```

Copy those files into the matching paths of an `autonomous_researcher` checkout
when applying the integration there. See the full integration guide:

- [Autonomous Researcher Integration](docs/autonomous_researcher_integration.md)

## Repository Layout

```text
UTM_VISION/
  src/compression_tester_monitor/   ROS 2 package for green-dot monitoring
  scripts/                          Shell commands and bashrc alias sample
  docs/                             Usage notes for camera, monitor, YOLO, bashrc
  patches/                          Local yolo_ros patch for class filtering
```

## Dependencies

ROS dependencies are declared in `src/compression_tester_monitor/package.xml`.

Python dependencies are listed in:

```text
src/compression_tester_monitor/requirements.txt
requirements.txt
```

The package assumes ROS 2 Lyrical, `usb_cam`, `cv_bridge`, OpenCV, NumPy, and the local `yolo_ros` package.

## Install

Copy or keep this repository inside a ROS 2 workspace, then build:

```bash
cd ~/yolo_ros_ws
colcon build --symlink-install --packages-select compression_tester_monitor
source install/setup.bash
```

If using the external `mgonzs13/yolo_ros` package, apply the included patch if class filtering is needed:

```bash
cd ~/yolo_ros_ws/src/yolo_ros
git apply ~/yolo_ros_ws/UTM_VISION/patches/yolo_ros_person_filter.patch
cd ~/yolo_ros_ws
colcon build --symlink-install --packages-select yolo_ros yolo_bringup
```

## Run

Open three terminals after sourcing `~/.bashrc`.

Terminal 1:

```bash
camera_rect
```

`camera_rect` defaults to `pixel_format:=yuyv2rgb` to avoid MJPEG decoder artifacts on the BRIO camera. To test MJPEG again:

```bash
camera_rect pixel_format:=mjpeg2rgb
```

Terminal 2:

```bash
green_dot_monitoring
```

`utm` is also available as a shorter alias for the same command.

Terminal 3:

```bash
yolo
```

One-shot stack script for GUI/API launch:

```bash
~/yolo_ros_ws/UTM_VISION/scripts/start_utm_vision_stack.sh
```

The `autonomous_researcher` GUI calls this script through its UTM Vision Runtime
Loading button. The script starts `camera_rect`, `green_dot_monitor`, and `yolo`
in one process group and stops the full stack together.

For the GUI/API path, start the `autonomous_researcher` server and press:

```text
Device Workspaces -> UTM Vision Runtime -> Loading
```

The runtime status endpoint is:

```bash
curl http://127.0.0.1:7860/api/equipment/utm-runtime/status
```

Explicit commands:

```bash
ros2 launch compression_tester_monitor camera_rect.launch.py pixel_format:=yuyv2rgb
ros2 launch compression_tester_monitor green_dot_monitor.launch.py input_image_topic:=/camera/image_rect
ros2 launch yolo_bringup yolov8.launch.py input_image_topic:=/image_utm classes:=0 threshold:=0.7
```

## rqt Topics

Use `rqt-topic-fixed` or `rqt` to inspect:

```text
/camera/image_raw
/camera/image_rect
/image_utm
/compression_tester/state
/compression_tester/summary
/compression_tester/metrics
/compression_tester/green_points
/compression_tester/debug_image
/yolo/dbg_image
/yolo/detections
/yolo/tracking
```

Quick terminal checks:

```bash
ros2 topic hz /camera/image_rect
ros2 topic hz /image_utm
ros2 topic echo /compression_tester/summary
```

## Documentation

- [Camera](docs/camera.md)
- [Green Dot Monitoring](docs/green_dot_monitoring.md)
- [YOLO](docs/yolo.md)
- [bashrc Aliases](docs/bashrc.md)
- [Autonomous Researcher Integration](docs/autonomous_researcher_integration.md)
