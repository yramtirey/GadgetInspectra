import { useEffect, useRef, useState } from "react";
import * as ROSLIB from "roslib";
import "./App.css";
import { InspectionScene } from "./components/InspectionScene";

import type { InspectionStatus } from "./status";
import { createDemo, advanceDemo, reviewDemo, scenarios } from "./demo";

function formatName(name: string) {
  return name.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function describeState(status: InspectionStatus) {
  switch (status.state) {
    case "SYSTEM_READY": return "Ready for inspection";
    case "MOVING_TO_TARGET": return "Positioning scanner";
    case "INSPECTING": return "Scanning panel";
    case "WAITING_FOR_SENSOR": return "Waiting for scan reading";
    case "ANALYZING": return "Checking thickness";
    case "REVIEW_REQUIRED": return "Operator review required";
    case "REWORKING": return "Simulating rework";
    case "VERIFYING_REWORK": return "Starting verification scan";
    case "WAITING_FOR_VERIFICATION": return "Waiting for verification";
    case "INSPECTION_COMPLETE":
      return status.rework_performed ? "Rework verified" : "Inspection passed";
    case "INSPECTION_FAILED": return "Inspection failed";
    default: return formatName(status.state);
  }
}

function App() {
  const demoMode = new URLSearchParams(window.location.search).get("mode") !== "live";
  const [demo, setDemo] = useState(() => createDemo(0));
  const [playing, setPlaying] = useState(true);
  const [connected, setConnected] = useState(false);
  const [liveStatus, setStatus] = useState<InspectionStatus | null>(null);
  const [liveEvents, setEventLog] = useState<InspectionStatus[]>([]);

  const status = demoMode ? demo.status : liveStatus;
  const eventLog = demoMode ? demo.events : liveEvents;
  const available = demoMode || connected;

  useEffect(() => {
    if (!demoMode || !playing) return;
    const timer = window.setInterval(() => setDemo(advanceDemo), 1000);
    return () => window.clearInterval(timer);
  }, [demoMode, playing]);

  const reviewTopic = useRef<ROSLIB.Topic | null>(null);

  function submitReview(action: "approve_rework" | "reject") {
    if (demoMode) {
      setDemo((current) => reviewDemo(current, action));
      return;
    }
    if (!connected || status?.state !== "REVIEW_REQUIRED" || !status.run_id) return;
    reviewTopic.current?.publish({
      data: JSON.stringify({ run_id: status.run_id, inspection_id: status.inspection_id, action }),
    });
  }

  useEffect(() => {
    if (demoMode) return;
    let active = true;
    const ros = new ROSLIB.Ros({
      url: "ws://localhost:9090",
    });

    ros.on("connection", () => {
      if (active) setConnected(true);
    });

    ros.on("error", (error: unknown) => {
      console.error("ROS connection error:", error);
      if (active) {
        setConnected(false);
        setStatus(null);
        setEventLog([]);
      }
    });

    ros.on("close", () => {
      if (active) {
        setConnected(false);
        setStatus(null);
        setEventLog([]);
      }
    });

    reviewTopic.current = new ROSLIB.Topic({
      ros, name: "/inspection/review_action", messageType: "std_msgs/msg/String",
    });

    const statusTopic = new ROSLIB.Topic({
      ros,
      name: "/inspection/status",
      messageType: "std_msgs/msg/String",
    });

    statusTopic.subscribe((message: unknown) => {
      if (!active) return;
      const rawMessage = message as {
        data: string;
      };

      try {
        const nextStatus = JSON.parse(
          rawMessage.data,
        ) as InspectionStatus;

        setStatus(nextStatus);
        setEventLog((currentEvents) =>
          [nextStatus, ...currentEvents].slice(0, 8),
        );
      } catch (error) {
        console.error("Invalid inspection telemetry:", error);
      }
    });

    return () => {
      active = false;
      statusTopic.unsubscribe();
      reviewTopic.current?.unadvertise();
      reviewTopic.current = null;
      ros.close();
    };
  }, [demoMode]);

  const isAlert = Boolean(
    status?.defect_detected || status?.state === "INSPECTION_FAILED",
  );
  const minimumThickness = status?.minimum_thickness_mm;
  const thicknessText = typeof minimumThickness === "number"
    ? minimumThickness.toFixed(1)
    : null;
  const hasReading = thicknessText !== null;
  const threshold = status?.threshold_mm ?? 7.0;
  const thicknessResult = !hasReading
    ? "Awaiting scan"
    : status?.state === "INSPECTION_FAILED"
      ? "Inspection failed"
      : status?.defect_detected
        ? "Below threshold"
        : status?.rework_performed
          ? "Verified after rework"
          : "Within threshold";

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">{demoMode ? "SIMULATED ROBOTIC INSPECTION · BROWSER DEMO" : "SIMULATED ROBOTIC INSPECTION · LIVE ROS TELEMETRY"}</p>
          <h1>GadgetInspectra</h1>
        </div>

        <div className={`connection ${available ? "online" : "offline"}`}>
          <span className="connection-dot" />
          {demoMode ? "BROWSER SIMULATION" : connected ? "ROS ONLINE" : "ROS OFFLINE"}
        </div>
      </header>

      <section className="demo-controls" aria-label="Dashboard mode and simulation controls">
        <nav className="mode-links" aria-label="Dashboard mode">
          <a href="?mode=demo" aria-current={demoMode ? "page" : undefined}>Browser demo</a>
          <a href="?mode=live" aria-current={!demoMode ? "page" : undefined}>Live ROS</a>
          <a href="https://github.com/yramtirey/GadgetInspectra">Source on GitHub ↗</a>
          <a href="https://yramtirey.github.io/#personal-projects">Personal Projects ↗</a>
        </nav>
        <p>{demoMode
          ? "Runs entirely in your browser. Readings, robot motion, and rework are simulated; no ROS connection, physical hardware, or persistent audit log."
          : "Live mode connects to Rosbridge at ws://localhost:9090. Start the local ROS workflow and dashboard using the repository instructions; an HTTPS page may block an insecure WebSocket."}</p>
        {demoMode && <div className="demo-buttons">
          <label htmlFor="scenario">Scenario</label>
          <select id="scenario" value={demo.scenarioIndex} onChange={(event) => setDemo(createDemo(Number(event.target.value), demo.status.inspection_id + 1))}>
            {scenarios.map((scenario, index) => <option key={scenario.id} value={index}>{formatName(scenario.id)}</option>)}
          </select>
          <button onClick={() => setPlaying(!playing)}>{playing ? "Pause" : "Play"}</button>
          <button onClick={() => { setPlaying(false); setDemo(advanceDemo); }}>Next step</button>
          <button onClick={() => setDemo(createDemo(demo.scenarioIndex, demo.status.inspection_id + 1))}>Restart scenario</button>
          {status?.state === "WAITING_FOR_SENSOR" && demo.scenarioIndex === 3 && <span>Simulated timeout: {demo.waitTicks} / 8 seconds</span>}
        </div>}
      </section>

      <section className="dashboard-grid">
        <article className="hero-card">
          <div className="card-heading">
            <div>
              <p className="label">CURRENT INSPECTION</p>
              <h2>
                Inspection{" "}
                {status ? String(status.inspection_id).padStart(3, "0") : "---"}
              </h2>
            </div>

            <span className={`state-pill ${isAlert ? "alert" : ""}`}>
              {status ? describeState(status) : "Waiting for telemetry"}
            </span>
          </div>

          <p className="scene-caption">
            Simulated scenario: {status?.scenario_id ? formatName(status.scenario_id) : "Awaiting scan"}
          </p>
          <div className="review-actions" aria-label="Operator review">
            <p>{status?.state === "REVIEW_REQUIRED"
              ? "Thin spot detected. Paused until you approve simulated rework or reject this inspection."
              : "Review controls are available when a thin spot requires a decision."}</p>
            <button disabled={!available || status?.state !== "REVIEW_REQUIRED" || !status.run_id}
              onClick={() => submitReview("approve_rework")}>Approve simulated rework</button>
            <button disabled={!available || status?.state !== "REVIEW_REQUIRED" || !status.run_id}
              onClick={() => submitReview("reject")}>Reject inspection (no rework)</button>
          </div>

          <div className="robot-visual">
            <InspectionScene
              state={status?.state ?? "SYSTEM_READY"}
              defectDetected={status?.defect_detected ?? false}
            />
          </div>
          <p className="scene-caption">
            {demoMode
              ? "3D arm animation follows the browser simulation. Drag to explore."
              : connected && status
              ? "3D arm animation follows ROS status; motion and rework are simulated."
              : "3D preview · waiting for live ROS telemetry."}
          </p>

          <div className="progress-block">
            <div className="progress-copy">
              <span>Inspection progress</span>
              <strong>{status?.progress_percent ?? 0}%</strong>
            </div>

            <div className="progress-track">
              <div
                className="progress-fill"
                style={{
                  width: `${status?.progress_percent ?? 0}%`,
                }}
              />
            </div>
          </div>
        </article>

        <aside className="metrics-column">
          <article className="metric-card">
            <p className="label">SIMULATED SCANNER</p>
            <strong>{status ? formatName(status.robot) : "Awaiting telemetry"}</strong>
            <span>{demoMode ? "Browser-simulated inspection arm" : "ROS-driven inspection arm visualization"}</span>
          </article>

          <article className="metric-card">
            <p className="label">INSPECTION TARGET</p>
            <strong>{status ? formatName(status.target) : "Awaiting target"}</strong>
            <span>Panel thickness at three scan points</span>
          </article>

          <article className={`metric-card ${isAlert ? "danger-card" : ""}`}>
            <p className="label">THICKNESS CHECK</p>
            <strong>{thicknessResult}</strong>
            <span>
              {hasReading
                ? `Minimum: ${thicknessText} mm · Pass: ≥ ${threshold.toFixed(1)} mm`
                : `Pass threshold: ≥ ${threshold.toFixed(1)} mm`}
            </span>
            {hasReading && (
              <span className="scan-phase">
                {status?.measurement_phase === "verification"
                  ? "Verification scan after simulated rework"
                  : "Initial scan"}
              </span>
            )}
            {status?.measurements?.length ? (
              <div className="reading-list" aria-label="Thickness readings">
                {status.measurements.map(({ point, thickness_mm }) => (
                  <span
                    className={`reading-chip ${thickness_mm < threshold ? "below-threshold" : ""}`}
                    key={point}
                  >
                    {point}: {thickness_mm.toFixed(1)} mm
                  </span>
                ))}
              </div>
            ) : null}
            {status?.error_reason && <span className="error-reason">{status.error_reason}</span>}
          </article>
        </aside>

        <article className="event-card">
          <div className="card-heading">
            <div>
              <p className="label">{demoMode ? "SIMULATED STATUS" : "LIVE ROS STATUS"}</p>
              <h2>Recent inspection updates</h2>
            </div>
            <span>{eventLog.length} recent updates</span>
          </div>

          <div className="event-list">
            {eventLog.length === 0 ? (
              <p className="empty-state">
                Waiting for telemetry from the inspection controller.
              </p>
            ) : (
              eventLog.map((event, index) => (
                <div
                  className="event-row"
                  key={`${event.inspection_id}-${event.state}-${index}`}
                >
                  <span className={`event-marker ${event.defect_detected || event.state === "INSPECTION_FAILED" ? "alert" : ""}`} />
                  <div>
                    <strong>{describeState(event)}</strong>
                    <p>
                      Inspection {event.inspection_id} · {formatName(event.target)}
                      {typeof event.minimum_thickness_mm === "number"
                        ? ` · Minimum ${event.minimum_thickness_mm.toFixed(1)} mm`
                        : ""}
                    </p>
                  </div>
                  <span>{event.progress_percent}%</span>
                </div>
              ))
            )}
          </div>
        </article>
      </section>
    </main>
  );
}

export default App;
