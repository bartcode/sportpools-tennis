export type Role = "player" | "joker" | "kluns";

export interface PoolPlayer {
  player: string;
  seed: number;
  black: number;
  section: number;
  potency: number;
  joker_bonus: number;
  kluns_penalty: number;
  /** Win probabilities for matches 1..7 (r64..w). */
  probs: number[];
}

export interface TeamPlayer extends PoolPlayer {
  role: Role;
}

export interface Team {
  players: TeamPlayer[];
  joker: string;
  kluns: string;
  expected_points: number;
}

export interface RouteStep {
  round: number;
  opponent: string;
  p_opponent: number;
  p_meet: number;
  p_reach: number;
  p_beat?: number;
}

export interface Matchup {
  a: string;
  b: string;
  round: number;
  p_meet: number;
}

export interface JokerOption {
  player: string;
  seed: number;
  black: number;
  p_r4: number;
  joker_bonus: number;
  potency: number;
}

export interface KlunsOption {
  kluns: string;
  black: number;
  e_penalty: number;
  team_ev: number;
}

export interface Coverage {
  exact: number;
  fuzzy: number;
  estimated: number;
  unmatched: string[];
}

export interface ReservePlayer {
  player: string;
  seed: number;
  black: number;
  potency: number;
  p_r4: number;
  p_w: number;
}

export interface ModelPayload {
  surface: string;
  label: string;
  team: Team;
  pool: PoolPlayer[];
  joker_options: JokerOption[];
  kluns_options: KlunsOption[];
  routes: Record<string, RouteStep[]>;
  matchups: Matchup[];
  reserves: ReservePlayer[];
  coverage: Coverage;
}

export interface PredictionResult {
  tournament: string;
  year: number;
  surfaces: string[];
  black_points: number;
  count: number;
  draw_source: string;
  ratings_source: string;
  sources: {
    draw_age_hours: number | null;
    ratings_age_hours: number | null;
  };
  models: Record<string, ModelPayload>;
}

export interface JobStatus {
  id: string;
  status: "pending" | "running" | "done" | "error";
  progress: number;
  stage: string;
  error?: string;
}

export interface EvaluateBreakdownRow {
  player: string;
  seed: number;
  black: number;
  section: number;
  role: Role;
  contribution: number;
  potency: number;
  joker_bonus: number;
  kluns_penalty: number;
  probs: number[];
}

export interface EvaluateResult {
  valid: boolean;
  errors: string[];
  expected_points: number;
  black_points: {
    used: number;
    limit: number;
    kluns_recycled: number;
  };
  players: EvaluateBreakdownRow[];
}

export interface SavedTeam {
  id: number;
  name: string;
  tournament: string;
  year: number;
  surface: string;
  created_at: string;
  payload: {
    players: string[];
    joker: string;
    kluns: string;
  };
}

export interface TeamMember {
  player: string;
  role: Role;
  locked: boolean;
}
