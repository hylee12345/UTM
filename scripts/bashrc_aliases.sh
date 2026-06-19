# UTM_VISION bashrc snippet

source /opt/ros/lyrical/setup.bash

if [ -f "$HOME/usb_cam_ws/install/setup.bash" ]; then
    source "$HOME/usb_cam_ws/install/setup.bash"
fi

if [ -f "$HOME/yolo_ros_ws/install/setup.bash" ]; then
    source "$HOME/yolo_ros_ws/install/setup.bash"
fi
if [ -f "$HOME/yolo_ros_ws/UTM_VISION/install/setup.bash" ]; then
    source "$HOME/yolo_ros_ws/UTM_VISION/install/setup.bash"
fi

alias camera_rect='$HOME/.local/bin/camera_rect'
alias green_dot_monitoring='ros2 launch compression_tester_monitor green_dot_monitor.launch.py input_image_topic:=/camera/image_rect'
alias utm='ros2 launch compression_tester_monitor green_dot_monitor.launch.py input_image_topic:=/camera/image_rect'
alias yolo='ros2 launch yolo_bringup yolov8.launch.py input_image_topic:=/image_utm classes:=0'
