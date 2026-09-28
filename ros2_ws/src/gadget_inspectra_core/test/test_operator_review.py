"""Exercise review decisions over real ROS topics with accelerated workflow ticks."""

from datetime import datetime
import json
import time

from gadget_inspectra_core.inspection_controller import InspectionController
from gadget_inspectra_core.thickness_sensor import ThicknessSensor
import pytest
import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String


@pytest.fixture
def system(tmp_path, monkeypatch):
    monkeypatch.setenv('GADGET_INSPECTION_AUDIT_LOG', str(tmp_path / 'audit.jsonl'))
    monkeypatch.delenv('GADGET_INSPECTION_SCENARIOS', raising=False)
    rclpy.init()
    controller = InspectionController()
    controller.timer.cancel()
    sensor = ThicknessSensor()
    client = Node('review_test_client')
    publisher = client.create_publisher(String, '/inspection/review_action', 10)
    executor = SingleThreadedExecutor()
    for node in (controller, sensor, client):
        executor.add_node(node)

    def spin_until(predicate):
        deadline = time.monotonic() + 5
        while not predicate() and time.monotonic() < deadline:
            executor.spin_once(timeout_sec=0.02)
        assert predicate(), 'ROS topic delivery timed out'

    spin_until(lambda: publisher.get_subscription_count() == 1
               and controller.scan_publisher.get_subscription_count() == 1
               and sensor.publisher.get_subscription_count() == 1)
    yield controller, publisher, executor, spin_until
    executor.shutdown()
    for node in (controller, sensor, client):
        node.destroy_node()
    rclpy.shutdown()


def start_scan(controller, spin_until, inspection_id=2):
    controller.inspection_id = inspection_id
    for _ in range(3):
        controller.run_workflow_step()
    spin_until(lambda: controller.state == 'ANALYZING')
    controller.run_workflow_step()


def send_decision(controller, publisher, action):
    publisher.publish(String(data=json.dumps({
        'run_id': controller.run_id,
        'inspection_id': controller.inspection_id,
        'action': action,
    })))


@pytest.mark.parametrize('action,inspection_id,outcome', [
    ('approve_rework', 2, 'pass'),
    ('approve_rework', 3, 'fail'),
    ('reject', 2, 'fail'),
])
def test_review_paths_and_audit(system, action, inspection_id, outcome):
    controller, publisher, executor, spin_until = system
    start_scan(controller, spin_until, inspection_id)
    for _ in range(12):
        controller.run_workflow_step()
    assert controller.state == 'REVIEW_REQUIRED'
    assert not controller.rework_performed
    assert controller.pending_phase is None
    assert not controller.audit_path.exists()

    send_decision(controller, publisher, action)
    spin_until(lambda: controller.operator_action is not None)
    timestamp = controller.operator_action_at
    assert datetime.fromisoformat(timestamp).utcoffset().total_seconds() == 0
    send_decision(controller, publisher, 'reject' if action == 'approve_rework'
                  else 'approve_rework')
    for _ in range(10):
        executor.spin_once(timeout_sec=0.02)
    assert controller.operator_action == action
    assert controller.operator_action_at == timestamp

    if action == 'approve_rework':
        assert controller.state == 'REWORKING'
        assert not controller.verification_measurements
        controller.run_workflow_step()
        controller.run_workflow_step()
        spin_until(lambda: controller.state in ('INSPECTION_COMPLETE', 'INSPECTION_FAILED'))
        assert controller.verification_measurements
        assert controller.rework_performed
    else:
        assert controller.state == 'INSPECTION_FAILED'
        assert not controller.rework_performed
        assert not controller.verification_measurements
    controller.run_workflow_step()
    records = [json.loads(line) for line in controller.audit_path.read_text().splitlines()]
    assert len(records) == 1
    record = records[0]
    assert record['decision'] == outcome
    assert record['operator_action'] == action
    assert record['operator_action_at'] == timestamp
    assert record['simulated_rework'] == (action == 'approve_rework')
    assert bool(record['verification_measurements']) == (action == 'approve_rework')
    assert controller.operator_action is None


def test_invalid_stale_and_out_of_state_actions(system):
    controller, publisher, executor, spin_until = system
    send_decision(controller, publisher, 'approve_rework')
    for _ in range(10):
        executor.spin_once(timeout_sec=0.02)
    assert controller.state == 'SYSTEM_READY'
    assert controller.operator_action is None
    start_scan(controller, spin_until)
    valid = {'run_id': controller.run_id, 'inspection_id': 2, 'action': 'approve_rework'}
    invalid = ['{', 'null', '[]', json.dumps({}), *[
        json.dumps({**valid, **change}) for change in (
            {'run_id': 'previous-run'}, {'inspection_id': 1},
            {'inspection_id': True}, {'inspection_id': 2.0},
            {'action': 'approve'}, {'action': []},
        )
    ]]
    for payload in invalid:
        publisher.publish(String(data=payload))
        for _ in range(3):
            executor.spin_once(timeout_sec=0.02)
        assert controller.state == 'REVIEW_REQUIRED'
        assert controller.operator_action is None


def test_clear_panel_and_sensor_timeout(system):
    controller, _, _, spin_until = system
    start_scan(controller, spin_until, 1)
    assert controller.state == 'INSPECTION_COMPLETE'
    controller.run_workflow_step()
    record = json.loads(controller.audit_path.read_text())
    assert record['operator_action'] is None
    assert record['operator_action_at'] is None
    controller.inspection_id = 4
    for _ in range(3):
        controller.run_workflow_step()
    controller.scan_started_at -= controller.SCAN_TIMEOUT_SECONDS
    controller.run_workflow_step()
    assert controller.state == 'INSPECTION_FAILED'
    assert controller.error_reason == 'Sensor response timed out'
