from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription(
        [
            Node(
                package="gadget_inspectra_core",
                executable="inspection_controller",
                name="inspection_controller",
                output="screen",
            ),
            Node(
                package="gadget_inspectra_core",
                executable="operator_console",
                name="operator_console",
                output="screen",
            ),
            Node(
                package="rosbridge_server",
                executable="rosbridge_websocket",
                name="rosbridge_websocket",
                output="screen",
                parameters=[
                    {
                        "port": 9090,
                        "address": "0.0.0.0",
                    }
                ],
            ),
            Node(
                package="gadget_inspectra_core",
                executable="thickness_sensor",
                name="thickness_sensor",
                output="screen",
            ),
        ]
    )