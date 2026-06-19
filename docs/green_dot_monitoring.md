# Green Dot Monitoring

`green_dot_monitoring` runs the `compression_tester_monitor` package.

It detects green marker dots inside a configurable ROI from `/camera/image_rect`, computes image-space coordinates, classifies the compression tester state, and publishes a full-size annotated image as `/image_utm`.

## Alias

```bash
alias green_dot_monitoring='ros2 launch compression_tester_monitor green_dot_monitor.launch.py input_image_topic:=/camera/image_rect'
alias utm='ros2 launch compression_tester_monitor green_dot_monitor.launch.py input_image_topic:=/camera/image_rect'
```

## Run

```bash
green_dot_monitoring
```

Equivalent command:

```bash
ros2 launch compression_tester_monitor green_dot_monitor.launch.py input_image_topic:=/camera/image_rect
```

## State Calculation

Detected green point centers are reduced to a bounding box:

```text
x_min = minimum x
x_max = maximum x
y_min = minimum y
y_max = maximum y
span_y = y_max - y_min
```

Default threshold:

```text
span_y <= 250 px -> WORKING
span_y > 250 px  -> NOT_WORKING
```

## Output Topics

```text
/image_utm
/compression_tester/state
/compression_tester/summary
/compression_tester/metrics
/compression_tester/green_points
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
ros2 launch compression_tester_monitor green_dot_monitor.launch.py \
  input_image_topic:=/camera/image_rect \
  working_height_threshold_px:=250.0 \
  use_roi:=True \
  roi_x_min:=180 roi_x_max:=410 \
  roi_y_min:=0 roi_y_max:=0
```

The ROI uses source-image pixel coordinates. The current 640x480 rectified camera view limits only the x-axis around the compression tester markers: `x=180..410`. The y-axis is unrestricted with `roi_y_min:=0` and `roi_y_max:=0`, where `roi_y_max` of `0` means the full image height. The published `/image_utm` remains full-size unless `hide_outside_roi:=True` is selected.

## Check

```bash
ros2 topic hz /image_utm
ros2 topic echo /compression_tester/state
ros2 topic echo /compression_tester/summary
```
