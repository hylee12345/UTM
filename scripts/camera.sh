#!/usr/bin/env bash
set -euo pipefail

ros2 run usb_cam usb_cam_node_exe --ros-args -p framerate:=1.0
