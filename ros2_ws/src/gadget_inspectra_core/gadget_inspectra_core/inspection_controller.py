import json
import random

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class InspectionController(Node):
    """Controls a simulated industrial inspection and rework workflow."""

    def __init__(self):
        super().__init__("inspection_controller")

        self.status_publisher = self.create_publisher(
            String,
            "/inspection/status",
            10,
        )

        self.target = "asset_panel_A"
        self.inspection_id = 1
        self.state = "SYSTEM_READY"
        self.defect_detected = False
        self.defect_confidence = 0.0

        # Fixed seed makes the demonstration reproducible.
        self.random_generator = random.Random(42)

        self.progress_by_state = {
            "SYSTEM_READY": 0,
            "MOVING_TO_TARGET": 15,
            "INSPECTING": 35,
            "ANALYZING": 55,
            "DEFECT_DETECTED": 65,
            "REWORKING": 75,
            "VERIFYING_REWORK": 90,
            "INSPECTION_COMPLETE": 100,
        }

        self.timer = self.create_timer(2.0, self.run_workflow_step)
        self.get_logger().info("GadgetInspectra controller started.")

    def run_workflow_step(self):
        self.publish_status()
        self.transition_to_next_state()

    def publish_status(self):
        status = {
            "inspection_id": self.inspection_id,
            "robot": "inspection_arm_01",
            "target": self.target,
            "state": self.state,
            "progress_percent": self.progress_by_state[self.state],
            "defect_detected": self.defect_detected,
            "defect_confidence": round(self.defect_confidence, 3),
        }

        message = String()
        message.data = json.dumps(status)

        self.status_publisher.publish(message)
        self.get_logger().info(f"Published status: {message.data}")

    def transition_to_next_state(self):
        if self.state == "SYSTEM_READY":
            self.state = "MOVING_TO_TARGET"

        elif self.state == "MOVING_TO_TARGET":
            self.state = "INSPECTING"

        elif self.state == "INSPECTING":
            self.state = "ANALYZING"

        elif self.state == "ANALYZING":
            self.defect_confidence = self.random_generator.random()
            self.defect_detected = self.defect_confidence >= 0.5

            if self.defect_detected:
                self.state = "DEFECT_DETECTED"
            else:
                self.state = "INSPECTION_COMPLETE"

        elif self.state == "DEFECT_DETECTED":
            self.state = "REWORKING"

        elif self.state == "REWORKING":
            self.state = "VERIFYING_REWORK"

        elif self.state == "VERIFYING_REWORK":
            self.defect_detected = False
            self.state = "INSPECTION_COMPLETE"

        elif self.state == "INSPECTION_COMPLETE":
            self.inspection_id += 1
            self.defect_detected = False
            self.defect_confidence = 0.0
            self.state = "SYSTEM_READY"


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