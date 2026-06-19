# YOLO

YOLO runs after `green_dot_monitoring` and consumes `/image_utm`.

The current local `yolo` alias launches `yolov8.launch.py` with:

```text
input_image_topic:=/image_utm
classes:=0
threshold:=0.7
```

## Alias

```bash
alias yolo='ros2 launch yolo_bringup yolov8.launch.py input_image_topic:=/image_utm classes:=0 threshold:=0.7'
```

## Run

```bash
yolo
```

Equivalent command:

```bash
ros2 launch yolo_bringup yolov8.launch.py input_image_topic:=/image_utm classes:=0 threshold:=0.7
```

## Notes

The local `yolo_ros` workspace has been patched to support a `classes` parameter in `yolo_node`. The included patch is:

```text
patches/yolo_ros_person_filter.patch
```

The patched `yolov8.launch.py` defaults used during development:

```text
threshold = 0.7
device = cuda:0
input_image_topic = /image_raw
classes = 0
```

The alias overrides the input topic to `/image_utm`.
The alias keeps person-only detection with `classes:=0` and uses `threshold:=0.7` for stricter detections.

The one-shot GUI/API stack script passes an absolute model path:

```text
model:=/home/lee-junyoung/yolo_ros_ws/yolov8m.pt
```

This avoids failures where the GUI launches the stack from a working directory
that does not contain `yolov8m.pt`.

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
