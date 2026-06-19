# Camera

The `camera` command starts `usb_cam` and publishes `/image_raw` only. The current monitoring workflow uses `camera_rect`, which starts `usb_cam` with calibration, runs `image_proc/rectify_node`, and publishes `/camera/image_raw` plus `/camera/image_rect`.

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

## Rectified Camera

Use this for the UTM pipeline:

```bash
camera_rect
```

Equivalent command:

```bash
ros2 launch compression_tester_monitor camera_rect.launch.py pixel_format:=yuyv2rgb
```

`camera_rect` currently defaults to:

```text
video_device  = /dev/v4l/by-id/usb-046d_Logitech_BRIO_1CD057A6-video-index0
image_width   = 640
image_height  = 480
framerate     = 30.0
pixel_format  = yuyv2rgb
```

`yuyv2rgb` uses the camera's YUYV stream and converts it to RGB in `usb_cam`, so downstream ROS image encoding remains `rgb8`. This avoids the BRIO MJPEG decode errors such as `No JPEG data found in image`.

To compare with MJPEG again:

```bash
camera_rect pixel_format:=mjpeg2rgb
```

If `camera_rect` reports that the BRIO device is already in use, close any camera viewer, browser tab, or previous ROS process using the camera. If only PipeWire is holding the device, restart the user camera services:

```bash
systemctl --user restart pipewire wireplumber
```

## Output Topics

Important topics:

```text
/image_raw
/image_raw/compressed
/camera_info
/camera/image_raw
/camera/image_rect
/camera/camera_info
```

The current workflow uses `/camera/image_rect` as the input to `green_dot_monitoring`.

## Check

```bash
ros2 topic hz /image_raw
ros2 topic info /image_raw
ros2 topic hz /camera/image_rect
ros2 topic info /camera/image_rect
```

Expected rate for `camera_rect` is about 30 Hz unless the launch argument `framerate` is changed.
