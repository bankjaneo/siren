/** Typed client for the Flask API. Endpoints are documented in stream_audio.py. */

export interface PlayerStatus {
  is_paused: boolean;
  stream_active: boolean;
  connection_lost: boolean;
  files_count: number;
  chromecast_connected: boolean;
  selected_device: string | null;
  current_file_index: number;
  current_file: string | null;
  current_volume: number;
  /** Seconds into the current file, when playing; null when unknown. */
  stream_position: number | null;
  /** Duration of the current file in seconds, when streaming. */
  stream_duration: number | null;
}

export interface CastDevice {
  name: string;
  model: string;
  host: string;
  port: string;
}

export interface CommandResult {
  status: string;
  message?: string;
  [key: string]: unknown;
}

async function request<T>(endpoint: string): Promise<T> {
  const response = await fetch(endpoint);
  if (!response.ok) {
    throw new Error(`${endpoint} failed (HTTP ${response.status})`);
  }
  return (await response.json()) as T;
}

/** GET /status */
export function getStatus(): Promise<PlayerStatus> {
  return request<PlayerStatus>("/status");
}

/** GET /files */
export function getFiles(): Promise<{ files: string[]; current_file_index: number }> {
  return request("/files");
}

/** GET /devices */
export function getDevices(): Promise<{
  devices: CastDevice[];
  error?: string;
}> {
  return request("/devices");
}

/** GET /config */
export function getConfig(): Promise<{
  default_volume: number;
  current_volume: number;
}> {
  return request("/config");
}

/**
 * Invoke a command endpoint (/play, /pause, /volume/42, ...).
 * Resolves with the JSON payload; callers decide whether
 * `result.status` indicates success for their flow.
 */
export async function command(endpoint: string): Promise<CommandResult> {
  return request<CommandResult>(endpoint);
}

/** True when the payload reports a successful command. */
export function isOk(result: CommandResult): boolean {
  return ["success", "playing", "paused", "resumed", "stopped", "connected", "disconnected"].includes(
    result.status,
  );
}
