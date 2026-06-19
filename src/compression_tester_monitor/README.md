# compression_tester_monitor

ROS 2 Python package for monitoring a compression tester using green visual markers in a fixed camera view.

The node subscribes to a camera image, detects green marker dots with OpenCV, computes their bounding box, classifies the tester state from the marker height, and publishes an annotated image for the YOLO pipeline.

## Current Pipeline

```text
/camera/image_raw + /camera/camera_info
  -> image_proc/rectify_node
  -> /camera/image_rect
  -> compression_tester_monitor/green_dot_monitor
  -> /image_utm
  -> yolo_ros/yolo_node
  -> /yolo/dbg_image
```

The `yolo` alias is configured to launch YOLO with `input_image_topic:=/image_utm` and `classes:=0` for person-only detection.

## State Logic

The monitor finds green marker centers inside a fixed ROI and computes:

```text
x_min = minimum green marker x
x_max = maximum green marker x
y_min = minimum green marker y
y_max = maximum green marker y
span_y = y_max - y_min
```

Default classification:

```text
span_y <= 300 px  -> WORKING
span_y > 300 px   -> NOT_WORKING
not enough points -> UNKNOWN
```

The camera is assumed to be fixed, so the default ROI and pixel threshold are intentionally hard-coded defaults with ROS parameters for adjustment.

## Published Topics

| Topic | Type | Description |
| --- | --- | --- |
| `/image_utm` | `sensor_msgs/msg/Image` | Original image with marker centers, bounding box, and state label drawn by state color. |
| `/compression_tester/state` | `std_msgs/msg/String` | `WORKING`, `NOT_WORKING`, or `UNKNOWN`. |
| `/compression_tester/summary` | `std_msgs/msg/String` | JSON summary with state, point list, bbox values, and threshold. |
| `/compression_tester/metrics` | `std_msgs/msg/Float64MultiArray` | Numeric state and bbox metrics for plotting/logging. |
| `/compression_tester/green_points` | `geometry_msgs/msg/PolygonStamped` | Detected marker centers as image-space points. |
| `/compression_tester/debug_image` | `sensor_msgs/msg/Image` | Extra debug image with ROI and marker overlays. |

`/compression_tester/metrics.data` layout:

```text
[state_code, point_count, x_min, x_max, y_min, y_max, span_x, span_y, threshold]
```

`state_code` values:

```text
WORKING = 1
NOT_WORKING = 0
UNKNOWN = -1
```

## Build

From the workspace root:

```bash
cd ~/yolo_ros_ws
colcon build --symlink-install --packages-select compression_tester_monitor
source install/setup.bash
```

## Run

Normal workflow:

```bash
camera_rect
utm
yolo
```

Equivalent explicit commands:

```bash
ros2 launch compression_tester_monitor camera_rect.launch.py
ros2 launch compression_tester_monitor green_dot_monitor.launch.py
ros2 launch yolo_bringup yolov8.launch.py input_image_topic:=/image_utm classes:=0
```

## Parameters

State overlay colors use OpenCV BGR drawing:

```text
WORKING     -> red
NOT_WORKING -> blue
UNKNOWN     -> yellow
```

Launch parameters:

| Parameter | Default | Description |
| --- | ---: | --- |
| `input_image_topic` | `/camera/image_rect` | Rectified camera image topic. |
| `output_image_topic` | `/image_utm` | Annotated image topic for YOLO input. |
| `working_height_threshold_px` | `300.0` | `WORKING` if `span_y` is less than or equal to this value. |
| `marker_max_span_y` | `700.0` | Maximum vertical span accepted for one upper/lower marker cluster. |
| `roi_x_min` | `500` | ROI left boundary in pixels. |
| `roi_y_min` | `80` | ROI top boundary in pixels. |
| `roi_x_max` | `950` | ROI right boundary in pixels. |
| `roi_y_max` | `480` | ROI bottom boundary in pixels. |

Node-only parameters with defaults:

| Parameter | Default | Description |
| --- | ---: | --- |
| `min_points` | `2` | Minimum number of green points required for a valid state. |
| `min_area` | `40.0` | Minimum green contour area. |
| `max_area` | `1500.0` | Maximum green contour area. |
| `min_circularity` | `0.4` | Minimum contour circularity. |
| `sat_min` | `80` | Minimum HSV saturation for green mask. |
| `val_min` | `80` | Minimum HSV value for green mask. |

Example threshold override:

```bash
ros2 launch compression_tester_monitor green_dot_monitor.launch.py working_height_threshold_px:=280.0
```

Example ROI override:

```bash
ros2 launch compression_tester_monitor green_dot_monitor.launch.py \
  roi_x_min:=520 roi_y_min:=90 roi_x_max:=930 roi_y_max:=460
```

## rqt Checks

Use `rqt-topic-fixed` or `rqt` to inspect:

```text
/compression_tester/state
/compression_tester/summary
/compression_tester/metrics
/image_utm
/yolo/dbg_image
```

For a quick terminal check:

```bash
ros2 topic echo /compression_tester/summary
ros2 topic hz /image_utm
```

## Python Dependencies

See `requirements.txt` for non-ROS Python package names. ROS package dependencies are declared in `package.xml`.
