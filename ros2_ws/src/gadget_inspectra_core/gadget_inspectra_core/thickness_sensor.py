import json

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class ThicknessSensor(Node):
    """Responds to scan requests with simulated panel thickness readings."""

    def __init__(self):
        super().__init__("thickness_sensor")

        self.publisher = self.create_publisher(
            String, "/inspection/measurements", 10
        )
        self.subscription = self.create_subscription(
            String, "/inspection/scan_request", self.handle_scan_request, 10
        )

        self.get_logger().info("Simulated thickness sensor ready.")

    def handle_scan_request(self, message):
        try:
            request = json.loads(message.data)
            inspection_id = request["inspection_id"]
            target = request["target"]

            phase = request.get("phase", "initial")
            if phase not in {"initial", "verification"}:
                raise ValueError(f"Unknown scan phase: {phase}")

            if type(inspection_id) is not int or not isinstance(target, str):
                raise ValueError("Invalid inspection ID or target")

        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            self.get_logger().error(f"Invalid scan request: {error}")
            return

        readings = [8.2, 8.1, 8.3]

        # Even-numbered inspections have a simulated thin spot at P02.
        if inspection_id % 2 == 0:
            readings[1] = 6.4 if phase == "initial" else 8.0

        result = {
            "inspection_id": inspection_id,
            "target": target,
            "sensor": "simulated_ultrasonic_thickness",
            "units": "mm",
            "phase": phase,
            "points": [
                {"point": f"P{index:02d}", "thickness_mm": thickness}
                for index, thickness in enumerate(readings, start=1)
            ],
        }

        self.publisher.publish(String(data=json.dumps(result)))
        self.get_logger().info(
            f"Published {phase} simulated scan {inspection_id}: {readings} mm"
        )


def main(args=None):
    rclpy.init(args=args)
    sensor = ThicknessSensor()

    try:
        rclpy.spin(sensor)
    except KeyboardInterrupt:
        pass
    finally:
        sensor.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()