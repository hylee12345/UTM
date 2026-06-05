#!/usr/bin/env bash
set -euo pipefail

ros2 launch yolo_bringup yolov8.launch.py input_image_topic:=/image_utm
