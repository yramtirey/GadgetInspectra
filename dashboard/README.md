# GadgetInspectra dashboard

The dashboard displays live status from the GadgetInspectra ROS 2 inspection simulation. It shows three panel thickness readings against a 7.0 mm pass threshold, the current inspection state, recent updates, and an interactive 3D view of the simulated inspection arm.

The sensor readings, arm motion, and rework are simulated. The dashboard does not control a physical robot.

## Start the system

From the **repository root**, open two terminals.

**Terminal 1 — ROS 2**

```bash
cd ros2_ws
colcon build --symlink-install
source install/setup.bash
export GADGET_INSPECTION_SCENARIOS="$PWD/src/gadget_inspectra_core/gadget_inspectra_core/inspection_scenarios.json"
ros2 launch gadget_inspectra_core inspection_system.launch.py
```

**Terminal 2 — dashboard**

```bash
cd dashboard
npm ci
npm run dev -- --host 0.0.0.0
```

Open [http://localhost:5173](http://localhost:5173). If you are using a development container, forward port 5173 to your browser. The browser also needs access to the Rosbridge WebSocket on port 9090; forward that port if necessary. The dashboard currently connects to `ws://localhost:9090`.

The connection badge shows **ROS ONLINE** after Rosbridge connects. With ROS offline, the dashboard shows a waiting state and clears old readings.

## What to expect

| Scenario | Initial readings (P01, P02, P03) | Outcome |
| --- | --- | --- |
| Clear panel | 8.2, 8.1, 8.3 mm | Pass: minimum 8.1 mm |
| Thin spot repaired | 8.2, 6.4, 8.3 mm | Simulated rework, then pass on a fresh 8.0 mm verification reading |
| Thin spot persists | 8.1, 6.6, 8.0 mm | Fail: verification still measures 6.8 mm at P02 |
| Sensor timeout | No reading | Fail: no sensor response within the timeout |

The dashboard subscribes to the ROS `/inspection/status` topic through Rosbridge. The controller publishes a JSON string containing the inspection ID, state, progress, readings, scan phase, threshold, and error reason. Drag the 3D view to rotate it; its animation follows the reported inspection state.

## Build

From `dashboard/`:

```bash
npm run build
```

For the complete ROS workflow and source layout, see the [project README](../README.md).
