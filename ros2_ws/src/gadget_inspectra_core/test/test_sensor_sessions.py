"""Test production callbacks deterministically and sensor output over real ROS topics."""

from copy import deepcopy
import json
import time
from uuid import uuid4

from gadget_inspectra_core import inspection_controller
from gadget_inspectra_core.inspection_controller import InspectionController
from gadget_inspectra_core.thickness_sensor import ThicknessSensor
import pytest
import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String


@pytest.fixture
def nodes(tmp_path, monkeypatch):
    monkeypatch.setenv('GADGET_INSPECTION_AUDIT_LOG', str(tmp_path / 'audit.jsonl'))
    monkeypatch.delenv('GADGET_INSPECTION_SCENARIOS', raising=False)
    rclpy.init()
    controller = InspectionController()
    controller.timer.cancel()
    sensor = ThicknessSensor()
    yield controller, sensor
    sensor.destroy_node()
    controller.destroy_node()
    rclpy.shutdown()


def message(payload):
    return String(data=json.dumps(payload))


def reading(controller, phase):
    return {
        'run_id': controller.run_id,
        'inspection_id': controller.inspection_id,
        'target': controller.target,
        'phase': phase,
        'scenario_id': 'thin_spot_repaired',
        'units': 'mm',
        'points': [
            {'point': f'P{index:02d}', 'thickness_mm': value}
            for index, value in enumerate([8.2, 8.0, 8.3], 1)
        ],
    }


def snapshot(controller):
    return deepcopy({key: getattr(controller, key) for key in (
        'state', 'pending_phase', 'scan_started_at', 'measurements',
        'initial_measurements', 'verification_measurements', 'measurement_phase',
        'minimum_thickness_mm', 'defect_detected', 'defect_confidence',
        'scenario_id', 'error_reason', 'operator_action', 'rework_performed',
    )})


@pytest.mark.parametrize('phase', ['initial', 'verification'])
@pytest.mark.parametrize('change', [
    {'run_id': str(uuid4())},  # Previous session, otherwise identical scan IDs.
    {},  # Missing token.
    {'run_id': ''}, {'run_id': None}, {'run_id': 'not-a-uuid'},
    {'run_id': 7}, {'run_id': True}, {'run_id': []}, {'run_id': {}},
    {'inspection_id': 99}, {'target': 'another_panel'}, {'phase': 'wrong'},
])
def test_rejected_reading_preserves_scan_then_valid_advances(nodes, phase, change):
    controller, _ = nodes
    if phase == 'verification':
        controller.request_scan('initial')
        controller.handle_measurement(message(reading(controller, 'initial')))
    controller.request_scan(phase)
    before = snapshot(controller)
    valid = reading(controller, phase)
    invalid = {**valid, **change}
    if not change:
        del invalid['run_id']
    controller.handle_measurement(message(invalid))
    assert snapshot(controller) == before
    assert not controller.audit_path.exists()

    controller.handle_measurement(message(valid))
    assert controller.state == (
        'ANALYZING' if phase == 'initial' else 'INSPECTION_COMPLETE'
    )
    assert controller.measurements == valid['points']
    assert controller.pending_phase is None
    assert controller.scan_started_at is None


@pytest.mark.parametrize('phase', ['initial', 'verification'])
def test_rejected_readings_leave_original_timeout(nodes, monkeypatch, phase):
    controller, _ = nodes
    now = [100.0]
    monkeypatch.setattr(inspection_controller.time, 'monotonic', lambda: now[0])
    controller.request_scan(phase)
    invalid = {**reading(controller, phase), 'run_id': str(uuid4())}
    now[0] = 107.0
    controller.handle_measurement(message(invalid))
    controller.run_workflow_step()
    assert controller.pending_phase == phase
    assert controller.scan_started_at == 100.0
    assert not controller.audit_path.exists()
    now[0] = 108.0
    controller.handle_measurement(message(invalid))
    controller.run_workflow_step()
    assert controller.state == 'INSPECTION_FAILED'
    assert controller.error_reason == 'Sensor response timed out'
    assert not controller.measurements
    assert not controller.audit_path.exists()
    controller.run_workflow_step()
    record = json.loads(controller.audit_path.read_text())
    assert record['decision'] == 'fail'
    assert record['initial_measurements'] == []
    assert record['verification_measurements'] == []


def test_unsolicited_reading_is_ignored(nodes):
    controller, _ = nodes
    before = snapshot(controller)
    controller.handle_measurement(message(reading(controller, 'initial')))
    assert snapshot(controller) == before
    assert not controller.audit_path.exists()


@pytest.mark.parametrize('token', [None, '', 'invalid', 1, True, [], {}])
def test_sensor_rejects_invalid_session(nodes, monkeypatch, token):
    controller, sensor = nodes
    published = []
    monkeypatch.setattr(sensor.publisher, 'publish', published.append)
    request = reading(controller, 'initial')
    request['run_id'] = token
    sensor.handle_scan_request(message(request))
    del request['run_id']
    sensor.handle_scan_request(message(request))
    assert published == []


@pytest.mark.parametrize('phase', ['initial', 'verification'])
def test_sensor_echoes_exact_request_session_over_ros(nodes, phase):
    controller, sensor = nodes
    client = Node('sensor_session_test_client')
    received = []
    client.create_subscription(
        String, '/inspection/measurements',
        lambda msg: received.append(json.loads(msg.data)), 10,
    )
    requests = []
    client.create_subscription(
        String, '/inspection/scan_request',
        lambda msg: requests.append(json.loads(msg.data)), 10,
    )
    executor = SingleThreadedExecutor()
    for node in (controller, sensor, client):
        executor.add_node(node)

    def spin_until(predicate):
        deadline = time.monotonic() + 5
        while not predicate() and time.monotonic() < deadline:
            executor.spin_once(timeout_sec=0.02)
        assert predicate(), 'ROS topic delivery timed out'

    try:
        spin_until(lambda: controller.scan_publisher.get_subscription_count() == 2
                   and sensor.publisher.get_subscription_count() == 2)
        controller.inspection_id = 2
        controller.request_scan(phase)
        spin_until(lambda: bool(received) and bool(requests))
        assert requests[0]['run_id'] == controller.run_id
        assert received[0]['run_id'] == requests[0]['run_id']
        assert received[0]['phase'] == phase
        # An old/noncanonical UUID is echoed exactly, never replaced or normalized.
        other_run = str(uuid4()).upper()
        sensor.handle_scan_request(message({**requests[0], 'run_id': other_run}))
        spin_until(lambda: len(received) == 2)
        assert received[1]['run_id'] == other_run
    finally:
        executor.shutdown()
        client.destroy_node()


def test_sensor_timeout_scenario_still_silent(nodes, monkeypatch):
    controller, sensor = nodes
    published = []
    monkeypatch.setattr(sensor.publisher, 'publish', published.append)
    controller.inspection_id = 4
    controller.request_scan('initial')
    sensor.handle_scan_request(message(reading(controller, 'initial')))
    assert published == []
    stale = {**reading(controller, 'initial'), 'run_id': str(uuid4())}
    controller.handle_measurement(message(stale))
    controller.scan_started_at -= controller.SCAN_TIMEOUT_SECONDS
    controller.run_workflow_step()
    assert controller.state == 'INSPECTION_FAILED'
    assert controller.error_reason == 'Sensor response timed out'


def test_delayed_reading_from_previous_controller_session(nodes):
    controller, _ = nodes
    previous = InspectionController()
    previous.timer.cancel()
    try:
        delayed = reading(previous, 'initial')
        assert previous.inspection_id == controller.inspection_id == 1
        assert previous.target == controller.target
        assert previous.run_id != controller.run_id
    finally:
        previous.destroy_node()
    controller.request_scan('initial')
    before = snapshot(controller)
    controller.handle_measurement(message(delayed))
    assert snapshot(controller) == before
    assert not controller.audit_path.exists()
