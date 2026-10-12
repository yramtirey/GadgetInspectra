"""Replay configurable thickness-inspection scenarios over ROS 2."""

import json
import math
import os
from pathlib import Path
from uuid import UUID

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


# These examples keep the node usable before a separate scenario file is installed.
DEFAULT_SCENARIOS = [
    {"id": "clear_panel", "initial": [8.2, 8.1, 8.3]},
    {
        "id": "thin_spot_repaired",
        "initial": [8.2, 6.4, 8.3],
        "verification": [8.2, 8.0, 8.3],
    },
    {
        "id": "thin_spot_persists",
        "initial": [8.1, 6.6, 8.0],
        "verification": [8.1, 6.8, 8.0],
    },
    {"id": "sensor_timeout", "initial": None},
]


def validate_scenarios(scenarios):
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("Scenarios must be a nonempty list")
    seen = set()
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            raise ValueError("Each scenario must be an object")
        scenario_id = scenario.get("id")
        if not isinstance(scenario_id, str) or not scenario_id or scenario_id in seen:
            raise ValueError("Each scenario needs a unique nonempty id")
        seen.add(scenario_id)
        if "initial" not in scenario:
            raise ValueError(f"{scenario_id}: missing initial readings")
        for phase in ("initial", "verification"):
            if phase not in scenario:
                continue
            readings = scenario[phase]
            if readings is None:  # Deliberately test the controller's timeout.
                continue
            if (
                not isinstance(readings, list)
                or len(readings) != 3
                or any(
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    or value <= 0
                    for value in readings
                )
            ):
                raise ValueError(f"{scenario_id}: {phase} needs three positive mm readings or null")
        if (
            scenario["initial"] is not None
            and min(scenario["initial"]) < 7.0
            and "verification" not in scenario
        ):
            raise ValueError(f"{scenario_id}: thin spot requires a verification scenario")
    return scenarios


def load_scenarios():
    configured_path = os.environ.get("GADGET_INSPECTION_SCENARIOS")
    if not configured_path:
        return validate_scenarios(DEFAULT_SCENARIOS)
    path = Path(configured_path).expanduser()
    with path.open(encoding="utf-8") as source:
        data = json.load(source)
    return validate_scenarios(data["scenarios"])


class ThicknessSensor(Node):
    """Respond to scan requests with readings from a labeled scenario."""

    def __init__(self):
        super().__init__("thickness_sensor")
        self.scenarios = load_scenarios()
        self.publisher = self.create_publisher(String, "/inspection/measurements", 10)
        self.subscription = self.create_subscription(
            String, "/inspection/scan_request", self.handle_scan_request, 10
        )
        self.get_logger().info(f"Loaded {len(self.scenarios)} simulated scan scenarios.")

    def handle_scan_request(self, message):
        try:
            request = json.loads(message.data)
            run_id = request['run_id']
            if not isinstance(run_id, str):
                raise ValueError('Expected a controller run UUID string')
            UUID(run_id)
            inspection_id = request["inspection_id"]
            target = request["target"]
            phase = request["phase"]
            if (
                type(inspection_id) is not int
                or inspection_id < 1
                or not isinstance(target, str)
                or not target
                or phase not in {"initial", "verification"}
            ):
                raise ValueError("Invalid inspection ID, target, or phase")
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            self.get_logger().error(f"Invalid scan request: {error}")
            return

        # A given inspection always uses the same scenario for both phases.
        scenario = self.scenarios[(inspection_id - 1) % len(self.scenarios)]
        readings = scenario.get(phase)
        if readings is None:
            self.get_logger().warning(
                f"Scenario {scenario['id']} simulates no {phase} sensor response."
            )
            return

        result = {
            'run_id': run_id,
            "inspection_id": inspection_id,
            "target": target,
            "sensor": "simulated_ultrasonic_thickness",
            "scenario_id": scenario["id"],
            "units": "mm",
            "phase": phase,
            "points": [
                {"point": f"P{index:02d}", "thickness_mm": value}
                for index, value in enumerate(readings, start=1)
            ],
        }
        self.publisher.publish(String(data=json.dumps(result)))
        self.get_logger().info(
            f"Scenario {scenario['id']} {phase} scan {inspection_id}: {readings} mm"
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
