#!/usr/bin/env bash
set -euo pipefail

ros2 launch compression_tester_monitor green_dot_monitor.launch.py \
  input_image_topic:=/camera/image_rect \
  use_roi:=True \
  roi_x_min:=1000 roi_x_max:=1450 \
  roi_y_min:=0 roi_y_max:=0 \
  hide_outside_roi:=False
