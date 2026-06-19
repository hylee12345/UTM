#!/usr/bin/env bash
set -euo pipefail

source_if_exists() {
  local setup_path="$1"
  if [[ -f "$setup_path" ]]; then
    # shellcheck disable=SC1090
    set +u
    source "$setup_path"
    set -u
  fi
}

source_if_exists /opt/ros/lyrical/setup.bash
source_if_exists "$HOME/image_pipeline_ws/install/setup.bash"
source_if_exists "$HOME/usb_cam_ws/install/setup.bash"
source_if_exists "$HOME/yolo_ros_ws/install/setup.bash"
source_if_exists "$HOME/yolo_ros_ws/UTM_VISION/install/setup.bash"

UTM_VISION_ROOT="${UTM_VISION_ROOT:-$HOME/yolo_ros_ws/UTM_VISION}"
YOLO_MODEL_PATH="${YOLO_MODEL_PATH:-/home/lee-junyoung/yolo_ros_ws/yolov8m.pt}"
CAMERA_STARTUP_DELAY_SEC="${UTM_CAMERA_STARTUP_DELAY_SEC:-2}"
MONITOR_STARTUP_DELAY_SEC="${UTM_MONITOR_STARTUP_DELAY_SEC:-1}"

pids=()

cleanup() {
  trap - INT TERM EXIT
  if (( ${#pids[@]} > 0 )); then
    kill -TERM "${pids[@]}" 2>/dev/null || true
    wait "${pids[@]}" 2>/dev/null || true
  fi
}

trap cleanup INT TERM EXIT

start_camera_rect() {
  if [[ -x "$HOME/.local/bin/camera_rect" ]]; then
    "$HOME/.local/bin/camera_rect"
    return
  fi
  ros2 launch compression_tester_monitor camera_rect.launch.py pixel_format:=yuyv2rgb
}

echo "[utm_vision_stack] starting camera_rect"
start_camera_rect &
pids+=("$!")
sleep "$CAMERA_STARTUP_DELAY_SEC"

echo "[utm_vision_stack] starting green_dot_monitor"
ros2 launch compression_tester_monitor green_dot_monitor.launch.py \
  input_image_topic:=/camera/image_rect \
  output_image_topic:=/image_utm \
  working_height_threshold_px:=250.0 \
  use_roi:=True \
  roi_x_min:=180 roi_x_max:=410 \
  roi_y_min:=0 roi_y_max:=0 \
  hide_outside_roi:=False &
pids+=("$!")
sleep "$MONITOR_STARTUP_DELAY_SEC"

echo "[utm_vision_stack] starting yolo"
ros2 launch yolo_bringup yolov8.launch.py \
  model:="$YOLO_MODEL_PATH" \
  input_image_topic:=/image_utm \
  classes:=0 \
  threshold:=0.7 &
pids+=("$!")

set +e
wait -n "${pids[@]}"
status="$?"
set -e
echo "[utm_vision_stack] child process exited with status ${status}; stopping stack"
cleanup
exit "$status"
