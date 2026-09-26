import json
import math
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class InspectionController(Node):
    """Run simulated thickness inspection, rework, and verification."""

    MINIMUM_ACCEPTABLE_THICKNESS_MM = 7.0
    SCAN_TIMEOUT_SECONDS = 8.0

    def __init__(self):
        super().__init__("inspection_controller")

        self.status_publisher = self.create_publisher(String, "/inspection/status", 10)
        self.scan_publisher = self.create_publisher(
            String, "/inspection/scan_request", 10
        )
        self.measurement_subscription = self.create_subscription(
            String, "/inspection/measurements", self.handle_measurement, 10
        )

        self.target = "asset_panel_A"
        self.inspection_id = 1
        self.progress_by_state = {
            "SYSTEM_READY": 0,
            "MOVING_TO_TARGET": 15,
            "INSPECTING": 30,
            "WAITING_FOR_SENSOR": 40,
            "ANALYZING": 55,
            "DEFECT_DETECTED": 65,
            "REWORKING": 75,
            "VERIFYING_REWORK": 85,
            "WAITING_FOR_VERIFICATION": 90,
            "INSPECTION_COMPLETE": 100,
            "INSPECTION_FAILED": 100,
        }
        self.reset_inspection()

        self.timer = self.create_timer(2.0, self.run_workflow_step)
        self.get_logger().info("GadgetInspectra controller started.")

    def reset_inspection(self):
        self.state = "SYSTEM_READY"
        self.defect_detected = False
        # Kept for compatibility with the current dashboard; this is a
        # threshold result, not a model confidence score.
        self.defect_confidence = 0.0
        self.rework_performed = False
        self.minimum_thickness_mm = None
        self.measurements = []
        self.measurement_phase = None
        self.pending_phase = None
        self.scan_started_at = None
        self.error_reason = None

    def publish_status(self):
        status = {
            "inspection_id": self.inspection_id,
            "robot": "inspection_arm_01",
            "target": self.target,
            "state": self.state,
            "progress_percent": self.progress_by_state[self.state],
            "defect_detected": self.defect_detected,
            "defect_confidence": self.defect_confidence,
            "rework_performed": self.rework_performed,
            "minimum_thickness_mm": self.minimum_thickness_mm,
            "threshold_mm": self.MINIMUM_ACCEPTABLE_THICKNESS_MM,
            "measurements": self.measurements,
            "measurement_phase": self.measurement_phase,
            "error_reason": self.error_reason,
        }
        message = String(data=json.dumps(status))
        self.status_publisher.publish(message)
        self.get_logger().info(f"Published status: {message.data}")

    def request_scan(self, phase):
        self.pending_phase = phase
        self.scan_started_at = time.monotonic()
        request = {
            "inspection_id": self.inspection_id,
            "target": self.target,
            "phase": phase,
        }
        self.state = (
            "WAITING_FOR_SENSOR"
            if phase == "initial"
            else "WAITING_FOR_VERIFICATION"
        )
        self.scan_publisher.publish(String(data=json.dumps(request)))
        self.get_logger().info(f"Requested {phase} scan.")

    def fail_inspection(self, reason):
        self.error_reason = reason
        self.pending_phase = None
        self.scan_started_at = None
        self.state = "INSPECTION_FAILED"
        self.get_logger().error(reason)

    def handle_measurement(self, message):
        if self.pending_phase is None:
            self.get_logger().warning("Ignoring unsolicited sensor reading.")
            return

        try:
            result = json.loads(message.data)
            if not isinstance(result, dict):
                raise ValueError("Expected an object")

            # A delayed response from a previous scan must not complete
            # the current scan or fail the current inspection.
            if (
                result.get("inspection_id") != self.inspection_id
                or result.get("target") != self.target
                or result.get("phase") != self.pending_phase
            ):
                self.get_logger().warning("Ignoring unrelated sensor reading.")
                return

            if result.get("units") != "mm":
                raise ValueError("Expected thickness readings in mm")
            points = result["points"]
            if not isinstance(points, list) or len(points) != 3:
                raise ValueError("Expected exactly three scan points")

            readings = []
            for index, point in enumerate(points, start=1):
                if not isinstance(point, dict) or point.get("point") != f"P{index:02d}":
                    raise ValueError("Unexpected scan point")
                value = point["thickness_mm"]
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError("Thickness must be a number")
                if not math.isfinite(value) or value <= 0:
                    raise ValueError("Thickness must be positive and finite")
                readings.append(value)

        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            self.fail_inspection(f"Invalid sensor reading: {error}")
            return

        phase = self.pending_phase
        self.pending_phase = None
        self.scan_started_at = None
        self.measurements = points
        self.measurement_phase = phase
        self.minimum_thickness_mm = min(readings)
        self.defect_detected = (
            self.minimum_thickness_mm < self.MINIMUM_ACCEPTABLE_THICKNESS_MM
        )
        self.defect_confidence = 1.0 if self.defect_detected else 0.0

        if phase == "initial":
            self.state = "ANALYZING"
        elif self.defect_detected:
            self.fail_inspection("Thin spot remains after simulated rework")
        else:
            self.state = "INSPECTION_COMPLETE"

        self.get_logger().info(
            f"{phase} scan: minimum thickness {self.minimum_thickness_mm:.1f} mm"
        )

    def run_workflow_step(self):
        self.publish_status()

        if self.state == "SYSTEM_READY":
            self.state = "MOVING_TO_TARGET"
        elif self.state == "MOVING_TO_TARGET":
            self.state = "INSPECTING"
        elif self.state == "INSPECTING":
            self.request_scan("initial")
        elif self.state in {"WAITING_FOR_SENSOR", "WAITING_FOR_VERIFICATION"}:
            if (
                self.scan_started_at is not None
                and time.monotonic() - self.scan_started_at >= self.SCAN_TIMEOUT_SECONDS
            ):
                self.fail_inspection("Sensor response timed out")
        elif self.state == "ANALYZING":
            self.state = (
                "DEFECT_DETECTED" if self.defect_detected else "INSPECTION_COMPLETE"
            )
        elif self.state == "DEFECT_DETECTED":
            self.state = "REWORKING"
        elif self.state == "REWORKING":
            self.rework_performed = True
            self.state = "VERIFYING_REWORK"
        elif self.state == "VERIFYING_REWORK":
            self.request_scan("verification")
        elif self.state in {"INSPECTION_COMPLETE", "INSPECTION_FAILED"}:
            self.inspection_id += 1
            self.reset_inspection()


def main(args=None):
    rclpy.init(args=args)
    controller = InspectionController()

    try:
        rclpy.spin(controller)
    except KeyboardInterrupt:
        pass
    finally:
        controller.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
