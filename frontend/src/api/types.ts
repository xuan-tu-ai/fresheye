// Shapes returned by the FastAPI backend; mirrors backend/app/schemas.py.

export type Action = "ANSWER" | "ASK_MORE" | "ABSTAIN";
export type Reason = "LOW_CONFIDENCE" | "UNFAMILIAR";
/** Ordinal freshness level: 0 = Rất tươi, 1 = Tươi, 2 = Không tươi. */
export type Level = 0 | 1 | 2;

export interface ImageOut {
  seq: number;
  label: Level;
  probs: [number, number, number];
  conf: number;
  strangeness: number;
  nearest_species: string;
  cam_peak: string;
  cam_center_share: number;
  cam_concentration: number;
  image_url: string;
  cam_url: string;
}

export interface DecisionOut {
  action: Action;
  /** Present only when action is ANSWER. */
  label: Level | null;
  probs: [number, number, number];
  conf: number;
  strangeness: number;
  nearest_species: string;
  n_images: number;
  reasons: Reason[];
}

export interface MessageOut {
  id: number;
  role: "user" | "assistant" | "tool";
  content: string;
  tool_name: string | null;
  created_at: string;
}

export interface InspectionOut {
  id: number;
  status: "open" | "closed";
  created_at: string;
  updated_at: string;
  decision: DecisionOut | null;
  images: ImageOut[];
  messages: MessageOut[];
}

export interface ImageUploadOut {
  inspection_id: number;
  status: "open" | "closed";
  image: ImageOut;
  decision: DecisionOut;
}

export interface StatsOut {
  total: number;
  by_action: Record<string, number>;
  by_label: Record<string, number>;
  avg_images: number;
  by_day: Record<string, number>;
  conf_hist: number[];
}

export interface PolicyOut {
  conf_threshold: number;
  strangeness_threshold: number;
  knn_k: number;
  max_images: number;
}

export interface HealthOut {
  status: string;
  device: string;
  device_name: string;
  checkpoint_exists: boolean;
  bank_loaded: boolean;
  policy: PolicyOut;
  ollama_reachable: boolean;
}
