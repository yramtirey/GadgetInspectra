import { useEffect, useState } from "react";
import * as ROSLIB from "roslib";
import "./App.css";
import { InspectionScene } from "./components/InspectionScene";

type InspectionStatus = {
  inspection_id: number;
  robot: string;
  target: string;
  state: string;
  progress_percent: number;
  defect_detected: boolean;
  defect_confidence: number;
};

function formatState(state: string) {
  return state.replace(/_/g, " ");
}

function App() {
  const [connected, setConnected] = useState(false);
  const [status, setStatus] = useState<InspectionStatus | null>(null);
  const [eventLog, setEventLog] = useState<InspectionStatus[]>([]);

  useEffect(() => {
    const ros = new ROSLIB.Ros({
      url: "ws://localhost:9090",
    });

    ros.on("connection", () => {
      setConnected(true);
    });

    ros.on("error", (error: unknown) => {
      console.error("ROS connection error:", error);
      setConnected(false);
    });

    ros.on("close", () => {
      setConnected(false);
    });

    const statusTopic = new ROSLIB.Topic({
      ros,
      name: "/inspection/status",
      messageType: "std_msgs/msg/String",
    });

    statusTopic.subscribe((message: unknown) => {
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
      statusTopic.unsubscribe();
      ros.close();
    };
  }, []);

  const isAlert =
    status?.state === "DEFECT_DETECTED" ||
    status?.state === "REWORKING";

  const confidence = status
    ? Math.round(status.defect_confidence * 100)
    : 0;

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">ROBOTIC INSPECTION PLATFORM</p>
          <h1>GadgetInspectra</h1>
        </div>

        <div className={`connection ${connected ? "online" : "offline"}`}>
          <span className="connection-dot" />
          {connected ? "ROS ONLINE" : "ROS OFFLINE"}
        </div>
      </header>

      <section className="dashboard-grid">
        <article className="hero-card">
          <div className="card-heading">
            <div>
              <p className="label">CURRENT MISSION</p>
              <h2>
                Inspection{" "}
                {status ? String(status.inspection_id).padStart(3, "0") : "---"}
              </h2>
            </div>

            <span className={`state-pill ${isAlert ? "alert" : ""}`}>
              {status ? formatState(status.state) : "WAITING FOR DATA"}
            </span>
          </div>

          <div className="robot-visual">
            <InspectionScene
              state={status?.state ?? "SYSTEM_READY"}
              defectDetected={status?.defect_detected ?? false}
            />
          </div>
          

          <div className="progress-block">
            <div className="progress-copy">
              <span>Mission progress</span>
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
            <p className="label">ROBOT</p>
            <strong>{status?.robot ?? "Awaiting connection"}</strong>
            <span>6-axis inspection manipulator</span>
          </article>

          <article className="metric-card">
            <p className="label">TARGET ASSET</p>
            <strong>{status?.target ?? "No target assigned"}</strong>
            <span>Active inspection region</span>
          </article>

          <article className={`metric-card ${isAlert ? "danger-card" : ""}`}>
            <p className="label">DEFECT ANALYSIS</p>
            <strong>
              {status?.defect_detected ? "Defect detected" : "No active defect"}
            </strong>
            <span>Model confidence: {confidence}%</span>
          </article>
        </aside>

        <article className="event-card">
          <div className="card-heading">
            <div>
              <p className="label">LIVE EVENT STREAM</p>
              <h2>System activity</h2>
            </div>
            <span>{eventLog.length} recent events</span>
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
                  <span className={`event-marker ${event.defect_detected ? "alert" : ""}`} />
                  <div>
                    <strong>{formatState(event.state)}</strong>
                    <p>
                      Inspection {event.inspection_id} · {event.target}
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