import scenarioData from '../../ros2_ws/src/gadget_inspectra_core/gadget_inspectra_core/inspection_scenarios.json';
import type { InspectionStatus } from './status';

// Reuse the ROS simulator's authored readings, not a second set of scenarios.
export const scenarios = scenarioData.scenarios;
export type Demo = {
  scenarioIndex: number;
  status: InspectionStatus;
  events: InspectionStatus[];
  waitTicks: number;
};

const progress: Record<string, number> = {
  SYSTEM_READY: 0, MOVING_TO_TARGET: 15, INSPECTING: 30,
  WAITING_FOR_SENSOR: 40, ANALYZING: 55, REVIEW_REQUIRED: 65,
  REWORKING: 75, VERIFYING_REWORK: 85, WAITING_FOR_VERIFICATION: 90,
  INSPECTION_COMPLETE: 100, INSPECTION_FAILED: 100,
};

export function createDemo(scenarioIndex: number, inspectionId = 1): Demo {
  const status: InspectionStatus = {
    run_id: 'browser-simulation', scenario_id: scenarios[scenarioIndex].id,
    inspection_id: inspectionId, robot: 'inspection_arm_01', target: 'asset_panel_A',
    state: 'SYSTEM_READY', progress_percent: 0, defect_detected: false,
    rework_performed: false, minimum_thickness_mm: null, threshold_mm: 7,
    measurements: [], measurement_phase: null, error_reason: null,
  };
  return { scenarioIndex, status, events: [status], waitTicks: 0 };
}

function transition(demo: Demo, state: string, changes: Partial<InspectionStatus> = {}): Demo {
  const status = { ...demo.status, ...changes, state, progress_percent: progress[state] };
  return { ...demo, status, events: [status, ...demo.events].slice(0, 8) };
}

function measure(demo: Demo, phase: 'initial' | 'verification'): Demo {
  const readings = scenarios[demo.scenarioIndex][phase];
  if (!readings) {
    const waiting = { ...demo, waitTicks: demo.waitTicks + 1 };
    return waiting.waitTicks < 8 ? waiting : transition(waiting, 'INSPECTION_FAILED', {
      error_reason: 'Sensor response timed out',
    });
  }
  const minimum = Math.min(...readings);
  const defect = minimum < demo.status.threshold_mm;
  return transition(demo, phase === 'initial' ? 'ANALYZING'
    : defect ? 'INSPECTION_FAILED' : 'INSPECTION_COMPLETE', {
    measurements: readings.map((value, index) => ({ point: `P0${index + 1}`, thickness_mm: value })),
    measurement_phase: phase, minimum_thickness_mm: minimum, defect_detected: defect,
    error_reason: phase === 'verification' && defect ? 'Thin spot remains after simulated rework' : null,
  });
}

export function advanceDemo(demo: Demo): Demo {
  switch (demo.status.state) {
    case 'SYSTEM_READY': return transition(demo, 'MOVING_TO_TARGET');
    case 'MOVING_TO_TARGET': return transition(demo, 'INSPECTING');
    case 'INSPECTING': return transition(demo, 'WAITING_FOR_SENSOR');
    case 'WAITING_FOR_SENSOR': return measure(demo, 'initial');
    case 'ANALYZING': return transition(demo, demo.status.defect_detected ? 'REVIEW_REQUIRED' : 'INSPECTION_COMPLETE');
    case 'REWORKING': return transition(demo, 'VERIFYING_REWORK', { rework_performed: true });
    case 'VERIFYING_REWORK': return { ...transition(demo, 'WAITING_FOR_VERIFICATION'), waitTicks: 0 };
    case 'WAITING_FOR_VERIFICATION': return measure(demo, 'verification');
    default: return demo; // Review and final results remain visible until user input.
  }
}

export function reviewDemo(demo: Demo, action: 'approve_rework' | 'reject'): Demo {
  if (demo.status.state !== 'REVIEW_REQUIRED') return demo;
  return action === 'approve_rework' ? transition(demo, 'REWORKING')
    : transition(demo, 'INSPECTION_FAILED', { error_reason: 'Operator rejected inspection without rework' });
}
