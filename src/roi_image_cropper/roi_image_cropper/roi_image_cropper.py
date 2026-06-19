from typing import Tuple
import time

import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image


class RoiImageCropper(Node):
    def __init__(self) -> None:
        super().__init__("roi_image_cropper")

        self.declare_parameter("input_image_topic", "/image_raw")
        self.declare_parameter("output_image_topic", "/compression_tester/roi/image")
        self.declare_parameter("x_min", 1000)
        self.declare_parameter("x_max", 1450)
        self.declare_parameter("y_min", 0)
        self.declare_parameter("y_max", 0)
        self.declare_parameter("diagnostic_logging", False)

        self.bridge = CvBridge()
        input_topic = str(self.get_parameter("input_image_topic").value)
        output_topic = str(self.get_parameter("output_image_topic").value)
        self.pub = self.create_publisher(Image, output_topic, 10)
        self.sub = self.create_subscription(Image, input_topic, self.image_cb, 10)
        self.frame_seq = 0
        self.last_input_wall = time.monotonic()

        self.get_logger().info(
            f"ROI image cropper started; {input_topic} -> {output_topic}"
        )

    def get_int_param(self, name: str) -> int:
        return int(float(self.get_parameter(name).value))

    def crop_bounds(self, width: int, height: int) -> Tuple[int, int, int, int]:
        x_min = self.get_int_param("x_min")
        x_max = self.get_int_param("x_max")
        y_min = self.get_int_param("y_min")
        y_max = self.get_int_param("y_max")

        if x_max <= 0:
            x_max = width
        if y_max <= 0:
            y_max = height

        x_min = max(0, min(width - 1, x_min))
        y_min = max(0, min(height - 1, y_min))
        x_max = max(x_min + 1, min(width, x_max))
        y_max = max(y_min + 1, min(height, y_max))
        return x_min, y_min, x_max, y_max

    def image_cb(self, msg: Image) -> None:
        cb_start_wall = time.monotonic()
        self.frame_seq += 1
        input_gap_ms = (cb_start_wall - self.last_input_wall) * 1000.0
        self.last_input_wall = cb_start_wall

        image = self.bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")
        height, width = image.shape[:2]
        x_min, y_min, x_max, y_max = self.crop_bounds(width, height)

        cropped = image[y_min:y_max, x_min:x_max].copy()
        cropped_msg = self.bridge.cv2_to_imgmsg(cropped, encoding=msg.encoding)
        cropped_msg.header = msg.header
        self.pub.publish(cropped_msg)

        process_ms = (time.monotonic() - cb_start_wall) * 1000.0
        if self.get_parameter("diagnostic_logging").value:
            if self.frame_seq % 30 == 0:
                self.get_logger().info(
                    f"roi_crop seq={self.frame_seq} input_gap_ms={input_gap_ms:.1f} "
                    f"process_ms={process_ms:.1f} input={width}x{height} "
                    f"crop={x_max - x_min}x{y_max - y_min}"
                )
            elif input_gap_ms > 150.0 or process_ms > 20.0:
                self.get_logger().warning(
                    f"roi_crop slow seq={self.frame_seq} input_gap_ms={input_gap_ms:.1f} "
                    f"process_ms={process_ms:.1f} input={width}x{height} "
                    f"crop={x_max - x_min}x{y_max - y_min}"
                )


def main(args=None) -> None:
    rclpy.init(args=args)
    node = RoiImageCropper()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
