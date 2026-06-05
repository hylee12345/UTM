# UTM_VISION bashrc snippet

source /opt/ros/lyrical/setup.bash

if [ -f "$HOME/usb_cam_ws/install/setup.bash" ]; then
    source "$HOME/usb_cam_ws/install/setup.bash"
fi

if [ -f "$HOME/yolo_ros_ws/install/setup.bash" ]; then
    source "$HOME/yolo_ros_ws/install/setup.bash"
fi

alias camera='ros2 run usb_cam usb_cam_node_exe --ros-args -p framerate:=1.0'
alias red_dot_monitoring='ros2 launch compression_tester_monitor red_dot_monitor.launch.py'
alias utm='ros2 launch compression_tester_monitor red_dot_monitor.launch.py'
alias yolo='ros2 launch yolo_bringup yolov8.launch.py input_image_topic:=/image_utm'
