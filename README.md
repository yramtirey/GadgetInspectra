# GadgetInspectra

GadgetInspectra is a **simulated robotic inspection system** built with ROS 2 and a browser dashboard. A controller requests simulated ultrasonic thickness readings, checks three points against a 7.0 mm minimum, and sends status updates to an operator console and an interactive 3D view. A detected thin spot pauses in `REVIEW_REQUIRED` until an operator approves simulated rework and a fresh verification scan, or rejects the inspection without rework.

The measurements and arm motion are simulated. The project demonstrates the software workflow and live telemetry; it does not control a physical robot or ultrasonic instrument.

## Why build it?

An inspection measurement is only useful if the system can turn it into a traceable decision. A panel with a thin point must not be accepted because the other points look good, a delayed reading must not be assigned to the next panel, and a failed scan must not quietly count as a pass. GadgetInspectra is a small testbed for those workflow problems: it keeps the sensor, inspection controller, operator display, and browser view as separate components and makes the decision state visible across them.

The current version exercises that workflow with four repeatable simulated scenarios and saves the resulting decisions. It demonstrates communication, threshold checks, and failure handling; it does **not** establish the accuracy of a thickness sensor or the reliability of a quality-control process. Those require representative measurements and evaluation against known outcomes.

## What it shows

- A ROS 2 controller coordinates inspection, analysis, operator review, simulated rework, verification, and failure states.
- A separate sensor node responds to scan requests with deterministic three-point thickness measurements.
- Editable scenario input can exercise both a verified repair and a repair that still fails the threshold, as well as a sensor timeout.
- The controller accepts only readings for the current controller session, inspection, target, and scan phase, validates the values, and times out if the sensor does not respond.
- An operator console reports measured values and the reason for each pass or failure.
- One audit record per completed inspection saves both sets of readings, the decision, its reason, and the operator action and UTC action time to a JSON Lines file.
- A React dashboard receives ROS status through Rosbridge WebSocket and shows the inspection state, three readings, threshold, event history, and a rotatable Three.js scene.

```mermaid
flowchart LR
    C[Inspection controller] -->|Scan request| S[Simulated sensor]
    S -->|Three readings| C
    C -->|Status| O[Operator console]
    C -->|Status| R[Rosbridge]
    R -->|WebSocket| D[React dashboard]
    D -->|Operator decision| R
    R -->|Review action| C
```

## Example inspection

The sensor replays four scenarios in order, then repeats the sequence. Its built-in examples are also provided in `inspection_scenarios.json` so the measurements can be edited without changing the Python node.

| Scenario | Initial readings at P01, P02, P03 | Decision | Verification |
| --- | --- | --- | --- |
| Clear panel | 8.2, 8.1, 8.3 mm | Pass; minimum 8.1 mm | Not needed |
| Thin spot repaired | 8.2, 6.4, 8.3 mm | P02 below 7.0 mm | After operator approval and simulated rework: 8.2, 8.0, 8.3 mm; pass |
| Thin spot persists | 8.1, 6.6, 8.0 mm | P02 below 7.0 mm | After operator approval and simulated rework: 8.1, 6.8, 8.0 mm; fail |
| Sensor timeout | No response | Fail after timeout | Not reached |

If a reading is invalid or the sensor does not respond within eight seconds, the controller marks that inspection as failed. The next cycle starts with a new inspection ID.

## Run locally

Use a development environment with ROS 2, `colcon`, the `gadget_inspectra_core` package dependencies, Rosbridge, Node.js, and npm. Run the two parts in separate terminals.

**Terminal 1 — ROS:**

```bash
cd ros2_ws
colcon build --symlink-install
source install/setup.bash
export GADGET_INSPECTION_SCENARIOS="$PWD/src/gadget_inspectra_core/gadget_inspectra_core/inspection_scenarios.json"
ros2 launch gadget_inspectra_core inspection_system.launch.py
```

The sensor can run without the `export` line, using the four scenarios built into its Python module. With the variable set, it reads the JSON file at startup; an invalid or missing file prevents the sensor node from starting. By default the controller appends final decisions to `~/.ros/gadget_inspectra_inspections.jsonl`. Set `GADGET_INSPECTION_AUDIT_LOG` before launch to use a different path. Each line is one JSON object, suitable for filtering by scenario, decision, and error reason.

**Terminal 2 — dashboard:**

```bash
cd dashboard
npm ci
npm run dev -- --host 0.0.0.0
```

Open `http://localhost:5173`. If you are using a development container, forward port `5173` to your browser. The browser must also reach Rosbridge on port `9090`; forward that port if needed. The dashboard connects to `ws://localhost:9090`, shows **ROS ONLINE** once it connects, and clears old telemetry if the connection closes.

To check the flow, approve simulated rework for both thin-spot scenarios using the dashboard buttons and watch four inspections: a direct pass, a verified pass after simulated rework, a failed verification, and a sensor timeout. Drag the 3D view to rotate it.

## Sensor-message contract

Scan requests on `/inspection/scan_request` and responses on `/inspection/measurements`
are JSON objects carried by `std_msgs/msg/String`. Both include `run_id` (the
controller startup UUID string), `inspection_id`, `target`, and `phase` (`initial`
or `verification`). The simulated sensor requires a UUID string and echoes the
exact received `run_id`; missing or malformed tokens are logged and receive no
response. The controller ignores responses whose token does not exactly match
its current session, including missing or malformed tokens, even if the other
scan identifiers match. These ignored responses leave accepted readings and the
pending scan's original timeout unchanged. This prevents delayed readings from
a previous controller session matching an inspection ID reused after restart.

## Operator review

Any initial reading below 7.0 mm leads to `REVIEW_REQUIRED`. The controller stays paused indefinitely, with no rework or verification request, until it accepts a decision. Exactly 7.0 mm passes the threshold. In the dashboard, choose **Approve simulated rework** to run simulated rework and request a fresh verification scan, or **Reject inspection (no rework)** to fail immediately without repair. Controls are disabled outside review and while ROS is offline. The simulated scenario name appears above the controls.

Clients can also publish a `std_msgs/msg/String` on `/inspection/review_action`. Its JSON payload must contain the current IDs from `/inspection/status`:

```json
{"run_id": "<current controller run UUID>", "inspection_id": 2, "action": "approve_rework"}
```

The other supported action is `reject`. Stale run/inspection IDs, duplicate decisions, malformed payloads, and actions outside review are ignored. The controller assigns the UTC `operator_action_at` timestamp when accepting `operator_action`; both fields appear in status and the terminal audit record (null when no review occurred). A rejection records a failure with no verification readings and `simulated_rework: false`. Approval does not guarantee a pass: verification can fail or time out. The console shows the paused state, scenario, current run ID, accepted action, and action time.

The audit file is appended when the terminal state is processed on the next controller tick. It is a local demonstration log, not a durable or authenticated operator-signoff system; stopping the process before that tick or a disk write failure can prevent recording.

## Verification

Build the ROS package as above, then run the behavioral tests from the repository root:

```bash
source ros2_ws/install/setup.bash
ROS_DOMAIN_ID=87 python3 -m pytest ros2_ws/src/gadget_inspectra_core/test/test_operator_review.py ros2_ws/src/gadget_inspectra_core/test/test_sensor_sessions.py -q
```

The operator-review tests and sensor propagation checks use real ROS topics in an isolated domain with accelerated controller ticks. Session rejection tests call production callbacks on real ROS nodes directly; timeout checks use a controlled clock or an adjusted scan deadline. Sensor silence checks capture publish calls. They cover the review pause, approved verification pass and failure, rejection, stale/invalid/duplicate decisions, audit fields, a clear panel, and sensor timeout. Build and lint the browser code with `npm run build` and `npm run lint` from `dashboard/`.

## Code layout

- `ros2_ws/src/gadget_inspectra_core/gadget_inspectra_core/inspection_controller.py` — workflow, threshold decision, scan validation, and status publication.
- `ros2_ws/src/gadget_inspectra_core/gadget_inspectra_core/thickness_sensor.py` — deterministic thickness readings for initial and verification scans.
- `ros2_ws/src/gadget_inspectra_core/gadget_inspectra_core/inspection_scenarios.json` — editable scenario readings; `null` simulates no sensor response.
- `ros2_ws/src/gadget_inspectra_core/gadget_inspectra_core/operator_console.py` — text updates for an operator.
- `ros2_ws/src/gadget_inspectra_core/launch/inspection_system.launch.py` — starts the ROS nodes and Rosbridge.
- `dashboard/src/App.tsx` — live status, readings, and recent updates.
- `dashboard/src/components/InspectionScene.tsx` — state-driven 3D arm and target visualization.

## Scope and limits

This is a software demonstration with synthetic thickness readings. The 3D arm follows workflow states; its motion is not a planned robot trajectory. “Rework” changes the simulated verification reading, without performing a physical repair. The `defect_confidence` field remains in ROS status for compatibility with earlier dashboard code; it is a binary threshold result, **not** a machine-learning probability.

## Next milestone: inspection decisions under uncertain readings

The next version should add repeated readings at each location and independent reference labels. The controller could then distinguish a clear pass, a clear thin spot, and a borderline reading that needs another scan or operator review. The current examples are authored test cases, not a representative inspection dataset.

Success would be measured against those reference labels: count missed thin spots, unnecessary reviews, and decisions made without sufficient readings. The current audit log records readings, decisions, reasons, and timestamps. Verification already uses a separate scenario reading and can fail; thin spots now pause for an explicit operator approval or rejection before any simulated rework.

This milestone would make the project a testable inspection decision system while remaining honest that its sensor and robot are simulated. A later integration could replace scenario input with recorded or live thickness measurements.
