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
                description="Input image topic to inspect",
            ),
            DeclareLaunchArgument(
                "output_image_topic",
                default_value="/image_utm",
                description="Annotated image topic with red marker bounding box",
            ),
            DeclareLaunchArgument(
                "working_height_threshold_px",
                default_value="300.0",
                description="WORKING if red marker y-span is less than or equal to this value",
            ),
            DeclareLaunchArgument(
                "roi_x_min",
                default_value="500",
                description="Left side of red marker region of interest",
            ),
            DeclareLaunchArgument(
                "roi_y_min",
                default_value="80",
                description="Top side of red marker region of interest",
            ),
            DeclareLaunchArgument(
                "roi_x_max",
                default_value="950",
                description="Right side of red marker region of interest",
            ),
            DeclareLaunchArgument(
                "roi_y_max",
                default_value="480",
                description="Bottom side of red marker region of interest",
            ),
            Node(
                package="compression_tester_monitor",
                executable="red_dot_monitor",
                name="red_dot_monitor",
                output="screen",
                parameters=[
                    {
                        "working_height_threshold_px": LaunchConfiguration(
                            "working_height_threshold_px"
                        ),
                        "roi_x_min": LaunchConfiguration("roi_x_min"),
                        "roi_y_min": LaunchConfiguration("roi_y_min"),
                        "roi_x_max": LaunchConfiguration("roi_x_max"),
                        "roi_y_max": LaunchConfiguration("roi_y_max"),
                        "output_image_topic": LaunchConfiguration("output_image_topic"),
                    }
                ],
                remappings=[
                    ("image", LaunchConfiguration("input_image_topic")),
                ],
            ),
        ]
    )
