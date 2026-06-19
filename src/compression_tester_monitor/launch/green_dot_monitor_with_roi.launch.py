from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "input_image_topic",
                default_value="/camera/image_rect",
                description="Rectified camera image topic to crop",
            ),
            DeclareLaunchArgument(
                "roi_image_topic",
                default_value="/compression_tester/roi/image",
                description="Cropped ROI image topic for the marker monitor",
            ),
            DeclareLaunchArgument(
                "output_image_topic",
                default_value="/image_utm",
                description="Annotated green marker monitor image topic",
            ),
            DeclareLaunchArgument(
                "diagnostic_logging",
                default_value="true",
                description="Enable timing logs for image processing",
            ),
            DeclareLaunchArgument(
                "roi_x_min",
                default_value="180",
                description="Left crop boundary in the raw image",
            ),
            DeclareLaunchArgument(
                "roi_x_max",
                default_value="410",
                description="Right crop boundary in the raw image",
            ),
            DeclareLaunchArgument(
                "roi_y_min",
                default_value="0",
                description="Top crop boundary in the raw image",
            ),
            DeclareLaunchArgument(
                "roi_y_max",
                default_value="0",
                description="Bottom crop boundary; 0 means full raw image height",
            ),
            Node(
                package="roi_image_cropper",
                executable="roi_image_cropper",
                name="roi_image_cropper",
                output="screen",
                parameters=[
                    {
                        "input_image_topic": LaunchConfiguration("input_image_topic"),
                        "output_image_topic": LaunchConfiguration("roi_image_topic"),
                        "x_min": LaunchConfiguration("roi_x_min"),
                        "x_max": LaunchConfiguration("roi_x_max"),
                        "y_min": LaunchConfiguration("roi_y_min"),
                        "y_max": LaunchConfiguration("roi_y_max"),
                    }
                ],
            ),
            Node(
                package="compression_tester_monitor",
                executable="green_dot_monitor",
                name="green_dot_monitor",
                output="screen",
                parameters=[
                    {
                        "output_image_topic": LaunchConfiguration("output_image_topic"),
                        "diagnostic_logging": LaunchConfiguration("diagnostic_logging"),
                        "use_x_roi": False,
                    }
                ],
                remappings=[
                    ("image", LaunchConfiguration("roi_image_topic")),
                ],
            ),
        ]
    )
