export type InspectionStatus = {
  run_id: string;
  scenario_id: string | null;
  inspection_id: number;
  robot: string;
  target: string;
  state: string;
  progress_percent: number;
  defect_detected: boolean;
  rework_performed: boolean;
  minimum_thickness_mm: number | null;
  threshold_mm: number;
  measurements: { point: string; thickness_mm: number }[];
  measurement_phase: "initial" | "verification" | null;
  error_reason: string | null;
};

