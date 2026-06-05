import json
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from geometry_msgs.msg import Point32, PolygonStamped
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import Float64MultiArray, String


@dataclass
class RedPoint:
    x: float
    y: float
    area: float
    circularity: float


class RedDotMonitor(Node):
    def __init__(self) -> None:
        super().__init__("red_dot_monitor")

        self.declare_parameter("working_height_threshold_px", 300.0)
        self.declare_parameter("min_points", 2)
        self.declare_parameter("min_area", 40.0)
        self.declare_parameter("max_area", 1500.0)
        self.declare_parameter("min_circularity", 0.4)
        self.declare_parameter("sat_min", 80)
        self.declare_parameter("val_min", 80)
        self.declare_parameter("roi_x_min", 500)
        self.declare_parameter("roi_y_min", 80)
        self.declare_parameter("roi_x_max", 950)
        self.declare_parameter("roi_y_max", 480)
        self.declare_parameter("output_image_topic", "/image_utm")

        self.bridge = CvBridge()
        output_image_topic = str(self.get_parameter("output_image_topic").value)

        self.state_pub = self.create_publisher(String, "/compression_tester/state", 10)
        self.summary_pub = self.create_publisher(String, "/compression_tester/summary", 10)
        self.metrics_pub = self.create_publisher(
            Float64MultiArray, "/compression_tester/metrics", 10
        )
        self.points_pub = self.create_publisher(
            PolygonStamped, "/compression_tester/red_points", 10
        )
        self.debug_pub = self.create_publisher(Image, "/compression_tester/debug_image", 10)
        self.output_image_pub = self.create_publisher(Image, output_image_topic, 10)

        self.sub = self.create_subscription(Image, "image", self.image_cb, 10)

        self.get_logger().info(f"Red dot monitor started; publishing {output_image_topic}")

    def state_color(self, state: str) -> Tuple[int, int, int]:
        if state == "WORKING":
            return (0, 0, 255)
        if state == "NOT_WORKING":
            return (255, 0, 0)
        return (0, 255, 255)

    def get_roi(self, width: int, height: int) -> Tuple[int, int, int, int]:
        x_min = int(self.get_parameter("roi_x_min").value)
        y_min = int(self.get_parameter("roi_y_min").value)
        x_max = int(self.get_parameter("roi_x_max").value)
        y_max = int(self.get_parameter("roi_y_max").value)

        x_min = max(0, min(width - 1, x_min))
        y_min = max(0, min(height - 1, y_min))
        x_max = max(x_min + 1, min(width, x_max))
        y_max = max(y_min + 1, min(height, y_max))
        return x_min, y_min, x_max, y_max

    def find_red_points(self, image: np.ndarray) -> Tuple[List[RedPoint], np.ndarray]:
        height, width = image.shape[:2]
        roi_x_min, roi_y_min, roi_x_max, roi_y_max = self.get_roi(width, height)
        roi = image[roi_y_min:roi_y_max, roi_x_min:roi_x_max]

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        sat_min = int(self.get_parameter("sat_min").value)
        val_min = int(self.get_parameter("val_min").value)

        lower_red = cv2.inRange(
            hsv,
            np.array([0, sat_min, val_min], dtype=np.uint8),
            np.array([12, 255, 255], dtype=np.uint8),
        )
        upper_red = cv2.inRange(
            hsv,
            np.array([165, sat_min, val_min], dtype=np.uint8),
            np.array([179, 255, 255], dtype=np.uint8),
        )
        mask = lower_red | upper_red

        kernel = np.ones((5, 5), dtype=np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        min_area = float(self.get_parameter("min_area").value)
        max_area = float(self.get_parameter("max_area").value)
        min_circularity = float(self.get_parameter("min_circularity").value)
        points: List[RedPoint] = []

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area or area > max_area:
                continue

            perimeter = cv2.arcLength(contour, True)
            circularity = 0.0
            if perimeter > 0.0:
                circularity = float(4.0 * np.pi * area / (perimeter * perimeter))
            if circularity < min_circularity:
                continue

            moment = cv2.moments(contour)
            if moment["m00"] == 0.0:
                continue

            x = float(moment["m10"] / moment["m00"] + roi_x_min)
            y = float(moment["m01"] / moment["m00"] + roi_y_min)
            points.append(RedPoint(x=x, y=y, area=float(area), circularity=circularity))

        points.sort(key=lambda point: (point.y, point.x))
        return points, mask

    def classify(self, points: List[RedPoint]) -> Tuple[str, Optional[dict]]:
        min_points = int(self.get_parameter("min_points").value)
        if len(points) < min_points:
            return "UNKNOWN", None

        xs = [point.x for point in points]
        ys = [point.y for point in points]
        x_min = min(xs)
        x_max = max(xs)
        y_min = min(ys)
        y_max = max(ys)
        span_x = x_max - x_min
        span_y = y_max - y_min

        threshold = float(self.get_parameter("working_height_threshold_px").value)
        state = "WORKING" if span_y <= threshold else "NOT_WORKING"
        return state, {
            "point_count": len(points),
            "x_min": x_min,
            "x_max": x_max,
            "y_min": y_min,
            "y_max": y_max,
            "span_x": span_x,
            "span_y": span_y,
            "working_height_threshold_px": threshold,
        }

    def publish_points(self, header, points: List[RedPoint]) -> None:
        msg = PolygonStamped()
        msg.header = header
        for point in points:
            msg.polygon.points.append(Point32(x=float(point.x), y=float(point.y), z=0.0))
        self.points_pub.publish(msg)

    def publish_metrics(self, state: str, metrics: Optional[dict]) -> None:
        msg = Float64MultiArray()
        state_code = {"UNKNOWN": -1.0, "NOT_WORKING": 0.0, "WORKING": 1.0}[state]
        if metrics is None:
            msg.data = [state_code, 0.0, -1.0, -1.0, -1.0, -1.0, 0.0, 0.0, 0.0]
        else:
            msg.data = [
                state_code,
                float(metrics["point_count"]),
                float(metrics["x_min"]),
                float(metrics["x_max"]),
                float(metrics["y_min"]),
                float(metrics["y_max"]),
                float(metrics["span_x"]),
                float(metrics["span_y"]),
                float(metrics["working_height_threshold_px"]),
            ]
        self.metrics_pub.publish(msg)

    def draw_debug(
        self,
        image: np.ndarray,
        state: str,
        metrics: Optional[dict],
        points: List[RedPoint],
    ) -> np.ndarray:
        debug = image.copy()
        roi_x_min, roi_y_min, roi_x_max, roi_y_max = self.get_roi(
            debug.shape[1], debug.shape[0]
        )
        cv2.rectangle(debug, (roi_x_min, roi_y_min), (roi_x_max, roi_y_max), (255, 0, 0), 2)

        for point in points:
            center = (round(point.x), round(point.y))
            cv2.circle(debug, center, 10, (0, 255, 255), 2)
            cv2.circle(debug, center, 3, (0, 255, 255), -1)

        if metrics is not None:
            min_pt = (round(metrics["x_min"]), round(metrics["y_min"]))
            max_pt = (round(metrics["x_max"]), round(metrics["y_max"]))
            cv2.rectangle(debug, min_pt, max_pt, (0, 255, 0), 2)
            text = (
                f"{state} points={metrics['point_count']} "
                f"height={metrics['span_y']:.1f}px "
                f"thr={metrics['working_height_threshold_px']:.1f}px"
            )
        else:
            text = f"{state} points={len(points)}"

        color = self.state_color(state)
        cv2.putText(debug, text, (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3)
        return debug

    def draw_output_image(
        self,
        image: np.ndarray,
        state: str,
        metrics: Optional[dict],
        points: List[RedPoint],
    ) -> np.ndarray:
        output = image.copy()
        color = self.state_color(state)

        for point in points:
            center = (round(point.x), round(point.y))
            cv2.circle(output, center, 7, color, -1)

        if metrics is not None:
            min_pt = (round(metrics["x_min"]), round(metrics["y_min"]))
            max_pt = (round(metrics["x_max"]), round(metrics["y_max"]))
            cv2.rectangle(output, min_pt, max_pt, color, 3)
            label = f"{state} h={metrics['span_y']:.1f}px"
            cv2.putText(
                output,
                label,
                (min_pt[0], max(30, min_pt[1] - 12)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                color,
                2,
            )

        return output

    def image_cb(self, msg: Image) -> None:
        image = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        points, _ = self.find_red_points(image)
        state, metrics = self.classify(points)

        state_msg = String()
        state_msg.data = state
        self.state_pub.publish(state_msg)

        summary = {"state": state}
        if metrics is not None:
            summary.update(metrics)
        else:
            summary["point_count"] = len(points)
        summary["points"] = [
            {
                "x": round(point.x, 2),
                "y": round(point.y, 2),
                "area": round(point.area, 2),
                "circularity": round(point.circularity, 3),
            }
            for point in points
        ]

        summary_msg = String()
        summary_msg.data = json.dumps(summary, sort_keys=True)
        self.summary_pub.publish(summary_msg)
        self.publish_metrics(state, metrics)
        self.publish_points(msg.header, points)

        output = self.draw_output_image(image, state, metrics, points)
        output_msg = self.bridge.cv2_to_imgmsg(output, encoding="bgr8")
        output_msg.header = msg.header
        self.output_image_pub.publish(output_msg)

        debug = self.draw_debug(output, state, metrics, points)
        debug_msg = self.bridge.cv2_to_imgmsg(debug, encoding="bgr8")
        debug_msg.header = msg.header
        self.debug_pub.publish(debug_msg)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = RedDotMonitor()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
