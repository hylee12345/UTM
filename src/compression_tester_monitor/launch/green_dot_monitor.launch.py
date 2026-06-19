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
                description="Rectified camera image topic to inspect",
            ),
            DeclareLaunchArgument(
                "output_image_topic",
                default_value="/image_utm",
                description="Annotated image topic with green marker bounding box",
            ),
            DeclareLaunchArgument(
                "diagnostic_logging",
                default_value="true",
                description="Enable timing logs for image processing",
            ),
            DeclareLaunchArgument(
                "working_height_threshold_px",
                default_value="250.0",
                description="WORKING if green marker y-span is less than or equal to this value",
            ),
            DeclareLaunchArgument(
                "use_roi",
                default_value="True",
                description="Restrict green marker detection to the configured ROI",
            ),
            DeclareLaunchArgument(
                "roi_x_min",
                default_value="180",
                description="Left ROI boundary in the source image",
            ),
            DeclareLaunchArgument(
                "roi_x_max",
                default_value="410",
                description="Right ROI boundary in the source image",
            ),
            DeclareLaunchArgument(
                "roi_y_min",
                default_value="0",
                description="Top ROI boundary in the source image",
            ),
            DeclareLaunchArgument(
                "roi_y_max",
                default_value="0",
                description="Bottom ROI boundary; 0 means full image height",
            ),
            DeclareLaunchArgument(
                "hide_outside_roi",
                default_value="False",
                description="Black out pixels outside the ROI in published images",
            ),
            DeclareLaunchArgument(
                "min_area",
                default_value="25.0",
                description="Minimum green marker contour area",
            ),
            DeclareLaunchArgument(
                "max_area",
                default_value="2500.0",
                description="Maximum green marker contour area",
            ),
            DeclareLaunchArgument(
                "sat_min",
                default_value="45",
                description="Minimum HSV saturation for green marker mask",
            ),
            DeclareLaunchArgument(
                "val_min",
                default_value="25",
                description="Minimum HSV value for green marker mask",
            ),
            DeclareLaunchArgument(
                "hue_min",
                default_value="55",
                description="Minimum HSV hue for green marker mask",
            ),
            DeclareLaunchArgument(
                "hue_max",
                default_value="95",
                description="Maximum HSV hue for green marker mask",
            ),
            DeclareLaunchArgument(
                "green_ratio_min",
                default_value="0.32",
                description="Minimum normalized green-channel dominance",
            ),
            DeclareLaunchArgument(
                "green_margin_min",
                default_value="5.0",
                description="Minimum green-channel margin over red and blue",
            ),
            DeclareLaunchArgument(
                "marker_max_span_x",
                default_value="360.0",
                description="Maximum x-span for one marker cluster",
            ),
            DeclareLaunchArgument(
                "marker_max_span_y",
                default_value="700.0",
                description="Maximum y-span for one marker cluster",
            ),
            DeclareLaunchArgument(
                "marker_cluster_padding_px",
                default_value="25.0",
                description="Search padding for green marker cluster selection",
            ),
            DeclareLaunchArgument(
                "marker_min_row_gap_px",
                default_value="45.0",
                description="Minimum y-gap between upper and lower marker rows",
            ),
            DeclareLaunchArgument(
                "marker_row_y_tolerance_px",
                default_value="35.0",
                description="Maximum y deviation inside one marker row",
            ),
            DeclareLaunchArgument(
                "marker_row_x_padding_px",
                default_value="70.0",
                description="Allowed x padding from the tightest marker row",
            ),
            DeclareLaunchArgument(
                "tracking_margin_px",
                default_value="55.0",
                description="Previous bbox expansion used to reject nearby green outliers",
            ),
            DeclareLaunchArgument(
                "max_lost_frames",
                default_value="5",
                description="Frames to keep the last valid bbox when markers are briefly lost",
            ),
            DeclareLaunchArgument(
                "max_bbox_jump_px",
                default_value="80.0",
                description="Maximum one-frame bbox coordinate jump before holding the last bbox",
            ),
            Node(
                package="compression_tester_monitor",
                executable="green_dot_monitor",
                name="green_dot_monitor",
                output="screen",
                parameters=[
                    {
                        "working_height_threshold_px": LaunchConfiguration(
                            "working_height_threshold_px"
                        ),
                        "use_x_roi": LaunchConfiguration("use_roi"),
                        "roi_x_min": LaunchConfiguration("roi_x_min"),
                        "roi_x_max": LaunchConfiguration("roi_x_max"),
                        "roi_y_min": LaunchConfiguration("roi_y_min"),
                        "roi_y_max": LaunchConfiguration("roi_y_max"),
                        "hide_outside_x_roi": LaunchConfiguration(
                            "hide_outside_roi"
                        ),
                        "min_area": LaunchConfiguration("min_area"),
                        "max_area": LaunchConfiguration("max_area"),
                        "sat_min": LaunchConfiguration("sat_min"),
                        "val_min": LaunchConfiguration("val_min"),
                        "hue_min": LaunchConfiguration("hue_min"),
                        "hue_max": LaunchConfiguration("hue_max"),
                        "green_ratio_min": LaunchConfiguration("green_ratio_min"),
                        "green_margin_min": LaunchConfiguration("green_margin_min"),
                        "marker_max_span_x": LaunchConfiguration("marker_max_span_x"),
                        "marker_max_span_y": LaunchConfiguration("marker_max_span_y"),
                        "marker_cluster_padding_px": LaunchConfiguration(
                            "marker_cluster_padding_px"
                        ),
                        "marker_min_row_gap_px": LaunchConfiguration(
                            "marker_min_row_gap_px"
                        ),
                        "marker_row_y_tolerance_px": LaunchConfiguration(
                            "marker_row_y_tolerance_px"
                        ),
                        "marker_row_x_padding_px": LaunchConfiguration(
                            "marker_row_x_padding_px"
                        ),
                        "tracking_margin_px": LaunchConfiguration("tracking_margin_px"),
                        "max_lost_frames": LaunchConfiguration("max_lost_frames"),
                        "max_bbox_jump_px": LaunchConfiguration("max_bbox_jump_px"),
                        "output_image_topic": LaunchConfiguration("output_image_topic"),
                        "diagnostic_logging": LaunchConfiguration("diagnostic_logging"),
                    }
                ],
                remappings=[
                    ("image", LaunchConfiguration("input_image_topic")),
                ],
            ),
        ]
    )
