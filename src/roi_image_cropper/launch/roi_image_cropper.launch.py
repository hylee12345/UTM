from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "input_image_topic",
                default_value="/image_raw",
                description="Raw input image topic",
            ),
            DeclareLaunchArgument(
                "output_image_topic",
                default_value="/compression_tester/roi/image",
                description="Cropped ROI output image topic",
            ),
            DeclareLaunchArgument(
                "x_min",
                default_value="1000",
                description="Left crop boundary in pixels",
            ),
            DeclareLaunchArgument(
                "x_max",
                default_value="1450",
                description="Right crop boundary in pixels",
            ),
            DeclareLaunchArgument(
                "y_min",
                default_value="0",
                description="Top crop boundary in pixels",
            ),
            DeclareLaunchArgument(
                "y_max",
                default_value="0",
                description="Bottom crop boundary in pixels; 0 means full image height",
            ),
            DeclareLaunchArgument(
                "diagnostic_logging",
                default_value="true",
                description="Enable timing logs for cropping",
            ),
            Node(
                package="roi_image_cropper",
                executable="roi_image_cropper",
                name="roi_image_cropper",
                output="screen",
                parameters=[
                    {
                        "input_image_topic": LaunchConfiguration("input_image_topic"),
                        "output_image_topic": LaunchConfiguration("output_image_topic"),
                        "x_min": LaunchConfiguration("x_min"),
                        "x_max": LaunchConfiguration("x_max"),
                        "y_min": LaunchConfiguration("y_min"),
                        "y_max": LaunchConfiguration("y_max"),
                        "diagnostic_logging": LaunchConfiguration("diagnostic_logging"),
                    }
                ],
            ),
        ]
    )
