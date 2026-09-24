import json

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class OperatorConsole(Node):
    """Displays robot telemetry and defect alerts to a field operator."""

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
            defect_detected = status["defect_detected"]
            confidence = status["defect_confidence"]

            summary = (
                f"Inspection {inspection_id} | "
                f"[{robot}] {state} | "
                f"Target: {target} | "
                f"Progress: {progress}%"
            )

            if state == "DEFECT_DETECTED":
                self.get_logger().warning(
                    f"{summary} | DEFECT ALERT "
                    f"(confidence: {confidence:.1%})"
                )

            elif state == "REWORKING":
                self.get_logger().warning(
                    f"{summary} | Autonomous rework in progress"
                )

            elif state == "VERIFYING_REWORK":
                self.get_logger().info(
                    f"{summary} | Verifying repaired region"
                )

            elif state == "INSPECTION_COMPLETE":
                result = "REWORKED" if confidence >= 0.5 else "PASSED"
                self.get_logger().info(
                    f"{summary} | Result: {result}"
                )

            else:
                self.get_logger().info(summary)

            if defect_detected and state not in {
                "DEFECT_DETECTED",
                "REWORKING",
            }:
                self.get_logger().warning(
                    "Defect remains active in the current workflow."
                )

        except (json.JSONDecodeError, KeyError, TypeError) as error:
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