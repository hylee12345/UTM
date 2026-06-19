# Camera

The camera command starts `usb_cam` and publishes `/image_raw`. The rectified workflow uses `camera_rect`, which publishes `/camera/image_raw` and `/camera/image_rect`.

## Alias

```bash
alias camera='ros2 run usb_cam usb_cam_node_exe --ros-args -p framerate:=1.0'
```

## Run

```bash
camera
```

Equivalent command:

```bash
ros2 run usb_cam usb_cam_node_exe --ros-args -p framerate:=1.0
```

## Output Topics

Important topics:

```text
/image_raw
/image_raw/compressed
/camera_info
```

The current workflow uses `/camera/image_rect` as the input to `green_dot_monitoring`.

## Check

```bash
ros2 topic hz /image_raw
ros2 topic info /image_raw
```

Expected rate with the current alias is about 1 Hz.
