#!/usr/bin/env bash
set -euo pipefail

ros2 launch compression_tester_monitor green_dot_monitor.launch.py \
  input_image_topic:=/camera/image_rect \
  working_height_threshold_px:=250.0 \
  use_roi:=True \
  roi_x_min:=180 roi_x_max:=410 \
  roi_y_min:=0 roi_y_max:=0 \
  hide_outside_roi:=False
