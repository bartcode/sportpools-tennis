import type {
  EvaluateResult,
  JobStatus,
  PredictionResult,
  SavedTeam,
  Team,
} from "@/types";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      // keep the status text
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export interface PredictBody {
  tournament: string;
  year: number;
  surfaces: string[];
  black_points: number;
  count: number;
  draw_url?: string;
  ratings_file?: string;
  cache_ttl: number;
}

export function startPrediction(body: PredictBody) {
  return api<{ job_id: string }>("/api/predict", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getJob(jobId: string) {
  return api<JobStatus>(`/api/jobs/${jobId}`);
}

export function getJobResult(jobId: string) {
  return api<PredictionResult>(`/api/jobs/${jobId}/result`);
}

/** The most recently cached prediction as a finished job (404 when none). */
export function getLatestPrediction() {
  return api<{ job_id: string }>("/api/predictions/latest");
}

export interface EvaluateBody {
  job_id: string;
  surface: string;
  players: string[];
  joker: string;
  kluns: string;
  black_points: number;
  count: number;
}

export function evaluateTeam(body: EvaluateBody) {
  return api<EvaluateResult>("/api/evaluate", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export interface OptimizeBody {
  job_id: string;
  surface: string;
  locked: string[];
  joker?: string;
  kluns?: string;
  black_points: number;
  count: number;
}

export function optimizeTeam(body: OptimizeBody) {
  return api<Team>("/api/optimize", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function listTeams() {
  return api<{ teams: SavedTeam[] }>("/api/teams");
}

export function saveTeam(body: {
  name: string;
  tournament: string;
  year: number;
  surface: string;
  players: string[];
  joker: string;
  kluns: string;
}) {
  return api<SavedTeam>("/api/teams", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function deleteTeam(id: number) {
  return api<{ deleted: number }>(`/api/teams/${id}`, { method: "DELETE" });
}

export interface TournamentInfo {
  key: string;
  label: string;
  years: number[];
  default_year: number;
}

export function getTournaments() {
  return api<{ tournaments: TournamentInfo[] }>("/api/tournaments");
}
