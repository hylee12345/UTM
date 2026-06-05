# Red Dot Monitoring

`red_dot_monitoring` runs the `compression_tester_monitor` package.

It detects red marker dots from `/image_raw`, computes image-space coordinates, classifies the compression tester state, and publishes an annotated image as `/image_utm`.

## Alias

```bash
alias red_dot_monitoring='ros2 launch compression_tester_monitor red_dot_monitor.launch.py'
alias utm='ros2 launch compression_tester_monitor red_dot_monitor.launch.py'
```

## Run

```bash
red_dot_monitoring
```

Equivalent command:

```bash
ros2 launch compression_tester_monitor red_dot_monitor.launch.py
```

## State Calculation

Detected red point centers are reduced to a bounding box:

```text
x_min = minimum x
x_max = maximum x
y_min = minimum y
y_max = maximum y
span_y = y_max - y_min
```

Default threshold:

```text
span_y <= 300 px -> WORKING
span_y > 300 px  -> NOT_WORKING
```

## Output Topics

```text
/image_utm
/compression_tester/state
/compression_tester/summary
/compression_tester/metrics
/compression_tester/red_points
/compression_tester/debug_image
```

`/image_utm` is the image that YOLO should consume.

## Overlay Colors

```text
WORKING     -> red bounding box
NOT_WORKING -> blue bounding box
UNKNOWN     -> yellow overlay
```

## Parameters

Common launch parameters:

```bash
ros2 launch compression_tester_monitor red_dot_monitor.launch.py \
  working_height_threshold_px:=300.0 \
  roi_x_min:=500 roi_y_min:=80 roi_x_max:=950 roi_y_max:=480
```

The ROI is hard-coded for the current fixed camera view but can be changed through launch parameters.

## Check

```bash
ros2 topic hz /image_utm
ros2 topic echo /compression_tester/state
ros2 topic echo /compression_tester/summary
```
