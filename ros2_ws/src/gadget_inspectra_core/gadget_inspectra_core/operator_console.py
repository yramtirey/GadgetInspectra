import json

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


STATE_LABELS = {
    "SYSTEM_READY": "Ready for inspection",
    "MOVING_TO_TARGET": "Positioning scanner",
    "INSPECTING": "Scanning panel",
    "WAITING_FOR_SENSOR": "Waiting for scan reading",
    "ANALYZING": "Checking thickness",
    "DEFECT_DETECTED": "Thin spot detected",
    "REWORKING": "Simulating rework",
    "VERIFYING_REWORK": "Starting verification scan",
    "WAITING_FOR_VERIFICATION": "Waiting for verification reading",
    "INSPECTION_COMPLETE": "Inspection complete",
    "INSPECTION_FAILED": "Inspection failed",
}


class OperatorConsole(Node):
    """Display simulated inspection telemetry and thickness results."""

    def __init__(self):
        super().__init__("operator_console")

        self.status_subscription = self.create_subscription(
            String,
            "/inspection/status",
            self.handle_status,
            10,
        )

        self.get_logger().info(
            "Operator console online. Waiting for inspection telemetry..."
        )

    def handle_status(self, message):
        try:
            status = json.loads(message.data)

            inspection_id = status["inspection_id"]
            robot = status["robot"]
            state = status["state"]
            target = status["target"]
            progress = status["progress_percent"]
            minimum = status.get("minimum_thickness_mm")
            threshold = status.get("threshold_mm")
            rework_performed = status.get("rework_performed", False)
            measurements = status.get("measurements") or []

            reading = ""
            if (
                isinstance(minimum, (int, float))
                and not isinstance(minimum, bool)
                and isinstance(threshold, (int, float))
                and not isinstance(threshold, bool)
            ):
                reading = (
                    f" | Minimum: {minimum:.1f} mm "
                    f"(pass threshold: ≥{threshold:.1f} mm)"
                )

            summary = (
                f"Inspection {inspection_id} | "
                f"[{robot.replace('_', ' ').title()}] "
                f"{STATE_LABELS.get(state, state.replace('_', ' ').title())} | "
                f"Target: {target.replace('_', ' ').title()} | "
                f"Progress: {progress}%{reading}"
            )

            if state == "DEFECT_DETECTED":
                thin_spots = [
                    f"{point['point']} at {point['thickness_mm']:.1f} mm"
                    for point in measurements
                    if isinstance(point, dict)
                    and isinstance(threshold, (int, float))
                    and isinstance(point.get("thickness_mm"), (int, float))
                    and point["thickness_mm"] < threshold
                ]
                location = f" | Thin spot: {', '.join(thin_spots)}" if thin_spots else ""
                self.get_logger().warning(
                    f"{summary}{location} | Below pass threshold"
                )

            elif state == "REWORKING":
                self.get_logger().warning(
                    f"{summary} | Simulated rework underway; verification pending"
                )

            elif state == "VERIFYING_REWORK":
                self.get_logger().info(
                    f"{summary} | Requesting a new thickness scan"
                )

            elif state == "INSPECTION_COMPLETE":
                result = (
                    "PASS after simulated rework and verification"
                    if rework_performed else "PASS"
                )
                self.get_logger().info(
                    f"{summary} | Result: {result}"
                )

            elif state == "INSPECTION_FAILED":
                reason = status.get("error_reason") or "Unknown reason"
                self.get_logger().error(f"{summary} | Result: FAIL | {reason}")

            else:
                self.get_logger().info(summary)

        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            self.get_logger().error(
                f"Invalid telemetry received: {error}"
            )


def main(args=None):
    rclpy.init(args=args)
    console = OperatorConsole()

    try:
        rclpy.spin(console)
    except KeyboardInterrupt:
        pass
    finally:
        console.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
