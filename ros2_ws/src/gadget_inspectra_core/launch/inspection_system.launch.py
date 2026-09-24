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
        ]
    )