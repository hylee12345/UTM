# YOLO

YOLO runs after `red_dot_monitoring` and consumes `/image_utm`.

The current local `yolo` alias launches `yolov8.launch.py` with:

```text
input_image_topic:=/image_utm
```

## Alias

```bash
alias yolo='ros2 launch yolo_bringup yolov8.launch.py input_image_topic:=/image_utm'
```

## Run

```bash
yolo
```

Equivalent command:

```bash
ros2 launch yolo_bringup yolov8.launch.py input_image_topic:=/image_utm
```

## Notes

The local `yolo_ros` workspace has been patched to support a `classes` parameter in `yolo_node`. The included patch is:

```text
patches/yolo_ros_person_filter.patch
```

The patched `yolov8.launch.py` defaults used during development:

```text
threshold = 0.9
device = cuda:0
input_image_topic = /image_raw
```

The alias overrides the input topic to `/image_utm`.

## Output Topics

```text
/yolo/detections
/yolo/tracking
/yolo/dbg_image
```

Check:

```bash
ros2 topic hz /yolo/dbg_image
ros2 topic echo /yolo/detections
```
