import json
import time
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
class GreenPoint:
    x: float
    y: float
    area: float
    circularity: float
    solidity: float
    aspect_ratio: float
    green_ratio: float
    green_margin: float


class GreenDotMonitor(Node):
    def __init__(self) -> None:
        super().__init__("green_dot_monitor")

        self.declare_parameter("working_height_threshold_px", 300.0)
        self.declare_parameter("min_points", 2)
        self.declare_parameter("min_area", 25.0)
        self.declare_parameter("max_area", 2500.0)
        self.declare_parameter("min_circularity", 0.25)
        self.declare_parameter("min_solidity", 0.55)
        self.declare_parameter("max_aspect_ratio", 3.5)
        self.declare_parameter("sat_min", 45)
        self.declare_parameter("val_min", 25)
        self.declare_parameter("hue_min", 55)
        self.declare_parameter("hue_max", 95)
        self.declare_parameter("green_ratio_min", 0.32)
        self.declare_parameter("green_margin_min", 5.0)
        self.declare_parameter("adaptive_thresholds", True)
        self.declare_parameter("adaptive_percentile", 90.0)
        self.declare_parameter("adaptive_sat_scale", 0.45)
        self.declare_parameter("adaptive_val_scale", 0.45)
        self.declare_parameter("adaptive_sat_floor", 45)
        self.declare_parameter("adaptive_val_floor", 12)
        self.declare_parameter("adaptive_green_margin_scale", 0.10)
        self.declare_parameter("adaptive_green_margin_floor", 5.0)
        self.declare_parameter("morph_open_size", 3)
        self.declare_parameter("morph_close_size", 5)
        self.declare_parameter("use_x_roi", False)
        self.declare_parameter("roi_x_min", 1000)
        self.declare_parameter("roi_x_max", 1450)
        self.declare_parameter("roi_y_min", 0)
        self.declare_parameter("roi_y_max", 0)
        self.declare_parameter("hide_outside_x_roi", False)
        self.declare_parameter("marker_max_span_x", 360.0)
        self.declare_parameter("marker_max_span_y", 700.0)
        self.declare_parameter("marker_cluster_padding_px", 25.0)
        self.declare_parameter("marker_min_row_gap_px", 45.0)
        self.declare_parameter("marker_row_y_tolerance_px", 35.0)
        self.declare_parameter("marker_row_x_padding_px", 70.0)
        self.declare_parameter("tracking_enabled", True)
        self.declare_parameter("tracking_margin_px", 55.0)
        self.declare_parameter("max_lost_frames", 5)
        self.declare_parameter("max_bbox_jump_px", 80.0)
        self.declare_parameter("max_jump_hold_frames", 3)
        self.declare_parameter("output_image_topic", "/image_utm")
        self.declare_parameter("diagnostic_logging", False)

        self.bridge = CvBridge()
        output_image_topic = str(self.get_parameter("output_image_topic").value)

        self.state_pub = self.create_publisher(String, "/compression_tester/state", 10)
        self.summary_pub = self.create_publisher(String, "/compression_tester/summary", 10)
        self.metrics_pub = self.create_publisher(
            Float64MultiArray, "/compression_tester/metrics", 10
        )
        self.points_pub = self.create_publisher(
            PolygonStamped, "/compression_tester/green_points", 10
        )
        self.debug_pub = self.create_publisher(Image, "/compression_tester/debug_image", 10)
        self.output_image_pub = self.create_publisher(Image, output_image_topic, 10)

        self.sub = self.create_subscription(Image, "image", self.image_cb, 10)

        self.last_state = "UNKNOWN"
        self.last_metrics: Optional[dict] = None
        self.last_points: List[GreenPoint] = []
        self.lost_frames = 0
        self.jump_hold_frames = 0
        self.frame_seq = 0
        self.last_input_wall = time.monotonic()

        self.get_logger().info(
            f"Green marker monitor started; publishing {output_image_topic}"
        )

    def get_bool_param(self, name: str) -> bool:
        value = self.get_parameter(name).value
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)

    def get_int_param(self, name: str) -> int:
        return int(float(self.get_parameter(name).value))

    def roi_bounds(self, width: int, height: int) -> Optional[Tuple[int, int, int, int]]:
        if not self.get_bool_param("use_x_roi"):
            return None

        x_min = self.get_int_param("roi_x_min")
        x_max = self.get_int_param("roi_x_max")
        y_min = self.get_int_param("roi_y_min")
        y_max = self.get_int_param("roi_y_max")
        if x_max <= 0:
            x_max = width
        if y_max <= 0:
            y_max = height
        if x_max <= x_min:
            return None
        if y_max <= y_min:
            return None

        x_min = max(0, min(width - 1, x_min))
        x_max = max(x_min + 1, min(width, x_max))
        y_min = max(0, min(height - 1, y_min))
        y_max = max(y_min + 1, min(height, y_max))
        return x_min, y_min, x_max, y_max

    def apply_x_roi_to_mask(self, mask: np.ndarray) -> np.ndarray:
        bounds = self.roi_bounds(mask.shape[1], mask.shape[0])
        if bounds is None:
            return mask

        x_min, y_min, x_max, y_max = bounds
        roi_mask = np.zeros_like(mask)
        roi_mask[y_min:y_max, x_min:x_max] = mask[y_min:y_max, x_min:x_max]
        return roi_mask

    def apply_x_roi_to_image(self, image: np.ndarray) -> np.ndarray:
        bounds = self.roi_bounds(image.shape[1], image.shape[0])
        if bounds is None:
            return image

        x_min, y_min, x_max, y_max = bounds
        if self.get_bool_param("hide_outside_x_roi"):
            output = np.zeros_like(image)
            output[y_min:y_max, x_min:x_max] = image[y_min:y_max, x_min:x_max]
        else:
            output = image.copy()
        cv2.rectangle(output, (x_min, y_min), (x_max, y_max), (0, 180, 0), 2)
        return output

    def state_color(self, state: str) -> Tuple[int, int, int]:
        if state == "WORKING":
            return (0, 0, 255)
        if state == "NOT_WORKING":
            return (255, 0, 0)
        return (0, 255, 255)

    def kernel_size(self, parameter_name: str) -> int:
        size = max(0, int(self.get_parameter(parameter_name).value))
        if size > 1 and size % 2 == 0:
            size += 1
        return size

    def adaptive_hsv_thresholds(self, hsv: np.ndarray) -> Tuple[int, int]:
        sat_min = int(self.get_parameter("sat_min").value)
        val_min = int(self.get_parameter("val_min").value)
        if not self.get_bool_param("adaptive_thresholds"):
            return sat_min, val_min

        percentile = float(self.get_parameter("adaptive_percentile").value)
        sat_scale = float(self.get_parameter("adaptive_sat_scale").value)
        val_scale = float(self.get_parameter("adaptive_val_scale").value)

        sat_dynamic = int(np.percentile(hsv[:, :, 1], percentile) * sat_scale)
        val_dynamic = int(np.percentile(hsv[:, :, 2], percentile) * val_scale)

        sat_floor = int(self.get_parameter("adaptive_sat_floor").value)
        val_floor = int(self.get_parameter("adaptive_val_floor").value)
        sat_threshold = max(sat_floor, min(sat_min, sat_dynamic))
        val_threshold = max(val_floor, min(val_min, val_dynamic))
        return sat_threshold, val_threshold

    def adaptive_green_margin(self, green_channel: np.ndarray) -> float:
        green_margin_min = float(self.get_parameter("green_margin_min").value)
        if not self.get_bool_param("adaptive_thresholds"):
            return green_margin_min

        margin_scale = float(self.get_parameter("adaptive_green_margin_scale").value)
        margin_floor = float(self.get_parameter("adaptive_green_margin_floor").value)
        dynamic_margin = float(np.percentile(green_channel, 90.0) * margin_scale)
        return min(green_margin_min, max(margin_floor, dynamic_margin))

    def build_marker_mask(
        self, image: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        sat_threshold, val_threshold = self.adaptive_hsv_thresholds(hsv)

        hue = hsv[:, :, 0]
        saturation = hsv[:, :, 1]
        value = hsv[:, :, 2]
        hue_min = int(self.get_parameter("hue_min").value)
        hue_max = int(self.get_parameter("hue_max").value)
        hue_mask = (hue >= hue_min) & (hue <= hue_max)
        hsv_mask = hue_mask & (saturation >= sat_threshold) & (value >= val_threshold)

        b_channel, g_channel, r_channel = cv2.split(image.astype(np.float32))
        green_ratio = g_channel / (r_channel + g_channel + b_channel + 1.0)
        green_margin = g_channel - np.maximum(r_channel, b_channel)
        green_ratio_min = float(self.get_parameter("green_ratio_min").value)
        green_margin_min = self.adaptive_green_margin(g_channel)
        dominance_mask = (green_ratio >= green_ratio_min) & (
            green_margin >= green_margin_min
        )

        mask = (hsv_mask & dominance_mask).astype(np.uint8) * 255

        open_size = self.kernel_size("morph_open_size")
        if open_size > 1:
            open_kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (open_size, open_size)
            )
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, open_kernel)

        close_size = self.kernel_size("morph_close_size")
        if close_size > 1:
            close_kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (close_size, close_size)
            )
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel)

        mask = self.apply_x_roi_to_mask(mask)
        return mask, green_ratio.astype(np.float32), green_margin.astype(np.float32)

    def find_green_points(
        self, image: np.ndarray
    ) -> Tuple[List[GreenPoint], np.ndarray]:
        mask, green_ratio, green_margin = self.build_marker_mask(image)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        min_area = float(self.get_parameter("min_area").value)
        max_area = float(self.get_parameter("max_area").value)
        min_circularity = float(self.get_parameter("min_circularity").value)
        min_solidity = float(self.get_parameter("min_solidity").value)
        max_aspect_ratio = float(self.get_parameter("max_aspect_ratio").value)
        green_ratio_min = float(self.get_parameter("green_ratio_min").value)
        green_margin_min = self.adaptive_green_margin(
            image[:, :, 1].astype(np.float32)
        )
        points: List[GreenPoint] = []

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

            x, y, w, h = cv2.boundingRect(contour)
            shortest_side = max(1, min(w, h))
            aspect_ratio = float(max(w, h) / shortest_side)
            if aspect_ratio > max_aspect_ratio:
                continue

            hull = cv2.convexHull(contour)
            hull_area = cv2.contourArea(hull)
            solidity = float(area / hull_area) if hull_area > 0.0 else 0.0
            if solidity < min_solidity:
                continue

            contour_mask = np.zeros(mask.shape, dtype=np.uint8)
            cv2.drawContours(contour_mask, [contour], -1, 255, -1)
            mean_green_ratio = float(cv2.mean(green_ratio, mask=contour_mask)[0])
            mean_green_margin = float(cv2.mean(green_margin, mask=contour_mask)[0])
            if (
                mean_green_ratio < green_ratio_min
                or mean_green_margin < green_margin_min
            ):
                continue

            moment = cv2.moments(contour)
            if moment["m00"] == 0.0:
                continue

            x = float(moment["m10"] / moment["m00"])
            y = float(moment["m01"] / moment["m00"])
            points.append(
                GreenPoint(
                    x=x,
                    y=y,
                    area=float(area),
                    circularity=circularity,
                    solidity=solidity,
                    aspect_ratio=aspect_ratio,
                    green_ratio=mean_green_ratio,
                    green_margin=mean_green_margin,
                )
            )

        points.sort(key=lambda point: (point.y, point.x))
        return points, mask

    def row_structure_score(self, points: List[GreenPoint]) -> float:
        if len(points) < 3:
            return 0.0

        min_row_gap = float(self.get_parameter("marker_min_row_gap_px").value)
        sorted_points = sorted(points, key=lambda point: point.y)
        best_score = 0.0
        for split_index in range(1, len(sorted_points)):
            top_row = sorted_points[:split_index]
            bottom_row = sorted_points[split_index:]
            row_gap = bottom_row[0].y - top_row[-1].y
            if row_gap < min_row_gap:
                continue

            top_span = top_row[-1].y - top_row[0].y if len(top_row) > 1 else 0.0
            bottom_span = (
                bottom_row[-1].y - bottom_row[0].y if len(bottom_row) > 1 else 0.0
            )
            balance = min(len(top_row), len(bottom_row))
            score = 700.0 + min(row_gap, 180.0) * 2.0 + balance * 250.0
            score -= (top_span + bottom_span) * 3.0
            best_score = max(best_score, score)

        return best_score

    def split_marker_rows(
        self, points: List[GreenPoint]
    ) -> Optional[Tuple[List[GreenPoint], List[GreenPoint]]]:
        if len(points) < 2:
            return None

        min_row_gap = float(self.get_parameter("marker_min_row_gap_px").value)
        sorted_points = sorted(points, key=lambda point: point.y)
        gaps = [
            (sorted_points[index + 1].y - sorted_points[index].y, index + 1)
            for index in range(len(sorted_points) - 1)
        ]
        if not gaps:
            return None

        row_gap, split_index = max(gaps, key=lambda item: item[0])
        if row_gap < min_row_gap:
            return None
        return sorted_points[:split_index], sorted_points[split_index:]

    def prune_marker_rows(self, points: List[GreenPoint]) -> List[GreenPoint]:
        min_points = int(self.get_parameter("min_points").value)
        rows = self.split_marker_rows(points)
        if rows is None:
            return points

        row_y_tolerance = float(self.get_parameter("marker_row_y_tolerance_px").value)
        y_pruned_rows: List[List[GreenPoint]] = []
        for row in rows:
            median_y = float(np.median([point.y for point in row]))
            y_pruned = [
                point for point in row if abs(point.y - median_y) <= row_y_tolerance
            ]
            y_pruned_rows.append(y_pruned if y_pruned else row)

        reference_rows = [row for row in y_pruned_rows if len(row) >= 2]
        if not reference_rows:
            pruned = [point for row in y_pruned_rows for point in row]
        else:
            reference_row = min(
                reference_rows,
                key=lambda row: max(point.x for point in row)
                - min(point.x for point in row),
            )
            x_padding = float(self.get_parameter("marker_row_x_padding_px").value)
            x_min = min(point.x for point in reference_row) - x_padding
            x_max = max(point.x for point in reference_row) + x_padding
            pruned = [
                point
                for row in y_pruned_rows
                for point in row
                if x_min <= point.x <= x_max
            ]

        if len(pruned) < min_points:
            return points
        pruned.sort(key=lambda point: (point.y, point.x))
        return pruned

    def cluster_score(self, points: List[GreenPoint]) -> float:
        xs = [point.x for point in points]
        ys = [point.y for point in points]
        span_x = max(xs) - min(xs)
        span_y = max(ys) - min(ys)
        total_area = sum(point.area for point in points)
        avg_margin = sum(point.green_margin for point in points) / len(points)
        avg_shape = sum(
            point.circularity + point.solidity for point in points
        ) / len(points)

        score = min(len(points), 5) * 1000.0
        score += total_area * 2.5
        score += avg_margin * 80.0
        score += avg_shape * 150.0
        score += self.row_structure_score(points)
        score -= span_x * 2.2
        score -= span_y * 0.5

        if self.last_metrics is not None:
            last_cx = (
                float(self.last_metrics["x_min"]) + float(self.last_metrics["x_max"])
            ) / 2.0
            last_cy = (
                float(self.last_metrics["y_min"]) + float(self.last_metrics["y_max"])
            ) / 2.0
            cluster_cx = (min(xs) + max(xs)) / 2.0
            cluster_cy = (min(ys) + max(ys)) / 2.0
            distance = float(np.hypot(cluster_cx - last_cx, cluster_cy - last_cy))
            score -= min(distance, 500.0) * 1.2

        return score

    def select_marker_cluster(self, points: List[GreenPoint]) -> List[GreenPoint]:
        min_points = int(self.get_parameter("min_points").value)
        if len(points) <= min_points:
            return points

        max_span_x = float(self.get_parameter("marker_max_span_x").value)
        max_span_y = float(self.get_parameter("marker_max_span_y").value)
        padding = float(self.get_parameter("marker_cluster_padding_px").value)

        best_points: List[GreenPoint] = []
        best_score = float("-inf")
        seen_clusters = set()

        for first in points:
            for second in points:
                center_x = (first.x + second.x) / 2.0
                center_y = (first.y + second.y) / 2.0
                x_min = center_x - max_span_x / 2.0 - padding
                x_max = center_x + max_span_x / 2.0 + padding
                y_min = center_y - max_span_y / 2.0 - padding
                y_max = center_y + max_span_y / 2.0 + padding

                cluster = [
                    point
                    for point in points
                    if x_min <= point.x <= x_max and y_min <= point.y <= y_max
                ]
                cluster = self.prune_marker_rows(cluster)
                if len(cluster) < min_points:
                    continue

                xs = [point.x for point in cluster]
                ys = [point.y for point in cluster]
                if max(xs) - min(xs) > max_span_x or max(ys) - min(ys) > max_span_y:
                    continue

                cluster_key = tuple(
                    sorted((round(point.x), round(point.y)) for point in cluster)
                )
                if cluster_key in seen_clusters:
                    continue
                seen_clusters.add(cluster_key)

                score = self.cluster_score(cluster)
                if score > best_score:
                    best_score = score
                    best_points = cluster

        if best_points:
            best_points.sort(key=lambda point: (point.y, point.x))
            return best_points
        return points

    def filter_points_by_previous(
        self, points: List[GreenPoint]
    ) -> List[GreenPoint]:
        if (
            not self.get_bool_param("tracking_enabled")
            or self.last_metrics is None
            or not points
        ):
            return points

        min_points = int(self.get_parameter("min_points").value)
        margin = float(self.get_parameter("tracking_margin_px").value)
        x_min = float(self.last_metrics["x_min"]) - margin
        x_max = float(self.last_metrics["x_max"]) + margin
        y_min = float(self.last_metrics["y_min"]) - margin
        y_max = float(self.last_metrics["y_max"]) + margin
        tracked_points = [
            point
            for point in points
            if x_min <= point.x <= x_max and y_min <= point.y <= y_max
        ]

        if len(tracked_points) >= min_points:
            if len(points) > len(tracked_points):
                rows = self.split_marker_rows(points)
                xs = [point.x for point in points]
                ys = [point.y for point in points]
                max_span_x = float(self.get_parameter("marker_max_span_x").value)
                max_span_y = float(self.get_parameter("marker_max_span_y").value)
                raw_span_y = max(ys) - min(ys)
                if (
                    rows is not None
                    and max(xs) - min(xs) <= max_span_x
                    and raw_span_y <= max_span_y
                ):
                    return points
            return tracked_points
        return points

    def classify(self, points: List[GreenPoint]) -> Tuple[str, Optional[dict]]:
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

    def bbox_jump(self, metrics: dict) -> float:
        if self.last_metrics is None:
            return 0.0
        keys = ("x_min", "x_max", "y_min", "y_max")
        return max(abs(float(metrics[key]) - float(self.last_metrics[key])) for key in keys)

    def stabilize_detection(
        self, state: str, metrics: Optional[dict], points: List[GreenPoint]
    ) -> Tuple[str, Optional[dict], List[GreenPoint], bool]:
        if not self.get_bool_param("tracking_enabled"):
            return state, metrics, points, False

        if metrics is None:
            max_lost_frames = int(self.get_parameter("max_lost_frames").value)
            if self.last_metrics is not None and self.lost_frames < max_lost_frames:
                self.lost_frames += 1
                return self.last_state, self.last_metrics, self.last_points, True

            self.last_state = state
            self.last_metrics = None
            self.last_points = []
            self.jump_hold_frames = 0
            return state, metrics, points, False

        max_bbox_jump = float(self.get_parameter("max_bbox_jump_px").value)
        max_jump_hold_frames = int(self.get_parameter("max_jump_hold_frames").value)
        if (
            self.last_metrics is not None
            and max_bbox_jump > 0.0
            and self.bbox_jump(metrics) > max_bbox_jump
            and self.jump_hold_frames < max_jump_hold_frames
        ):
            self.jump_hold_frames += 1
            return self.last_state, self.last_metrics, self.last_points, True

        self.last_state = state
        self.last_metrics = metrics
        self.last_points = points
        self.lost_frames = 0
        self.jump_hold_frames = 0
        return state, metrics, points, False

    def publish_points(self, header, points: List[GreenPoint]) -> None:
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
        points: List[GreenPoint],
        tracking_hold: bool = False,
    ) -> np.ndarray:
        debug = self.apply_x_roi_to_image(image.copy())

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
        if tracking_hold:
            text = f"{text} hold"

        color = self.state_color(state)
        cv2.putText(debug, text, (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3)
        return debug

    def draw_output_image(
        self,
        image: np.ndarray,
        state: str,
        metrics: Optional[dict],
        points: List[GreenPoint],
        tracking_hold: bool = False,
    ) -> np.ndarray:
        output = self.apply_x_roi_to_image(image.copy())
        color = self.state_color(state)

        for point in points:
            center = (round(point.x), round(point.y))
            cv2.circle(output, center, 7, color, -1)

        if metrics is not None:
            min_pt = (round(metrics["x_min"]), round(metrics["y_min"]))
            max_pt = (round(metrics["x_max"]), round(metrics["y_max"]))
            cv2.rectangle(output, min_pt, max_pt, color, 3)
            label = f"{state} h={metrics['span_y']:.1f}px"
            if tracking_hold:
                label = f"{label} hold"
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
        cb_start_wall = time.monotonic()
        self.frame_seq += 1
        input_gap_ms = (cb_start_wall - self.last_input_wall) * 1000.0
        self.last_input_wall = cb_start_wall

        image = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        raw_points, _ = self.find_green_points(image)
        selected_points = self.select_marker_cluster(raw_points)
        points = self.filter_points_by_previous(selected_points)
        state, metrics = self.classify(points)
        state, metrics, points, tracking_hold = self.stabilize_detection(
            state, metrics, points
        )

        state_msg = String()
        state_msg.data = state
        self.state_pub.publish(state_msg)

        summary = {"state": state}
        if metrics is not None:
            summary.update(metrics)
        else:
            summary["point_count"] = len(points)
        summary["raw_point_count"] = len(raw_points)
        summary["selected_point_count"] = len(selected_points)
        summary["tracking_hold"] = tracking_hold
        x_roi = self.roi_bounds(image.shape[1], image.shape[0])
        summary["x_roi"] = (
            {"enabled": False}
            if x_roi is None
            else {
                "enabled": True,
                "x_min": x_roi[0],
                "y_min": x_roi[1],
                "x_max": x_roi[2],
                "y_max": x_roi[3],
            }
        )
        summary["points"] = [
            {
                "x": round(point.x, 2),
                "y": round(point.y, 2),
                "area": round(point.area, 2),
                "circularity": round(point.circularity, 3),
                "solidity": round(point.solidity, 3),
                "aspect_ratio": round(point.aspect_ratio, 3),
                "green_ratio": round(point.green_ratio, 3),
                "green_margin": round(point.green_margin, 2),
            }
            for point in points
        ]

        summary_msg = String()
        summary_msg.data = json.dumps(summary, sort_keys=True)
        self.summary_pub.publish(summary_msg)
        self.publish_metrics(state, metrics)
        self.publish_points(msg.header, points)

        output = self.draw_output_image(image, state, metrics, points, tracking_hold)
        output_msg = self.bridge.cv2_to_imgmsg(output, encoding="bgr8")
        output_msg.header = msg.header
        self.output_image_pub.publish(output_msg)

        debug = self.draw_debug(output, state, metrics, points, tracking_hold)
        debug_msg = self.bridge.cv2_to_imgmsg(debug, encoding="bgr8")
        debug_msg.header = msg.header
        self.debug_pub.publish(debug_msg)

        cb_end_wall = time.monotonic()
        process_ms = (cb_end_wall - cb_start_wall) * 1000.0
        if self.get_bool_param("diagnostic_logging"):
            span_y = float(metrics["span_y"]) if metrics is not None else -1.0
            if self.frame_seq % 30 == 0:
                self.get_logger().info(
                    f"green_dot seq={self.frame_seq} input_gap_ms={input_gap_ms:.1f} "
                    f"process_ms={process_ms:.1f} raw={len(raw_points)} "
                    f"selected={len(selected_points)} kept={len(points)} state={state} "
                    f"hold={tracking_hold} span_y={span_y:.1f}"
                )
            elif input_gap_ms > 150.0 or process_ms > 50.0:
                span_y_text = f"{span_y:.1f}" if metrics is not None else "n/a"
                self.get_logger().warning(
                    f"green_dot slow seq={self.frame_seq} input_gap_ms={input_gap_ms:.1f} "
                    f"process_ms={process_ms:.1f} raw={len(raw_points)} "
                    f"selected={len(selected_points)} kept={len(points)} state={state} "
                    f"hold={tracking_hold} span_y={span_y_text}"
                )


def main(args=None) -> None:
    rclpy.init(args=args)
    node = GreenDotMonitor()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
