import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    default_calibration = os.path.expanduser(
        "~/.ros/camera_info/default_cam.yaml"
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "camera_info_url",
                default_value="file://" + default_calibration,
                description="Camera calibration YAML URL",
            ),
            DeclareLaunchArgument(
                "video_device",
                default_value="/dev/v4l/by-id/usb-046d_Logitech_BRIO_1CD057A6-video-index0",
                description="V4L2 camera device",
            ),
            DeclareLaunchArgument(
                "image_width",
                default_value="640",
                description="Camera image width",
            ),
            DeclareLaunchArgument(
                "image_height",
                default_value="480",
                description="Camera image height",
            ),
            DeclareLaunchArgument(
                "framerate",
                default_value="30.0",
                description="Camera frame rate",
            ),
            DeclareLaunchArgument(
                "brightness",
                default_value="128",
                description="Camera brightness control value",
            ),
            DeclareLaunchArgument(
                "gain",
                default_value="-1",
                description="Camera gain control value; -1 leaves it unchanged",
            ),
            DeclareLaunchArgument(
                "diagnostic_logging",
                default_value="true",
                description="Enable frame timing logs",
            ),
            Node(
                package="usb_cam",
                executable="usb_cam_node_exe",
                namespace="camera",
                name="usb_cam",
                output="screen",
                parameters=[
                    {
                        "video_device": LaunchConfiguration("video_device"),
                        "image_width": LaunchConfiguration("image_width"),
                        "image_height": LaunchConfiguration("image_height"),
                        "framerate": LaunchConfiguration("framerate"),
                        "brightness": LaunchConfiguration("brightness"),
                        "gain": LaunchConfiguration("gain"),
                        "pixel_format": "mjpeg2rgb",
                        "camera_name": "default_cam",
                        "camera_info_url": LaunchConfiguration("camera_info_url"),
                        "publish_camera_info": True,
                        "diagnostic_logging": LaunchConfiguration("diagnostic_logging"),
                    }
                ],
                remappings=[
                    ("/set_camera_info", "/camera/set_camera_info"),
                ],
            ),
            Node(
                package="image_proc",
                executable="rectify_node",
                namespace="camera",
                name="rectify_node",
                output="screen",
                parameters=[
                    {
                        "image_transport": "raw",
                        "diagnostic_logging": LaunchConfiguration("diagnostic_logging"),
                    }
                ],
                remappings=[
                    ("image", "image_raw"),
                    ("image_rect", "image_rect"),
                ],
            ),
        ]
    )
