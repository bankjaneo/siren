/** Shared reactive player state, kept fresh by polling /status every 2s. */

import { getStatus, type PlayerStatus } from "./api";

export const player = $state<{ data: PlayerStatus | null; error: string | null }>({
  data: null,
  error: null,
});

export type PlaybackState = "offline" | "stopped" | "paused" | "playing";

/** Derive the playback state from a status payload. */
export function playbackState(s: PlayerStatus | null): PlaybackState {
  if (!s || !s.chromecast_connected) return "offline";
  if (!s.stream_active) return "stopped";
  return s.is_paused ? "paused" : "playing";
}

let timer: ReturnType<typeof setInterval> | undefined;

/** Fetch /status once and update the shared store. */
export async function refreshStatus(): Promise<void> {
  try {
    player.data = await getStatus();
    player.error = null;
  } catch (error) {
    player.error = (error as Error).message;
  }
}

/** Start polling; safe to call repeatedly. */
export function startPolling(intervalMs = 2000): void {
  if (timer !== undefined) return;
  refreshStatus();
  timer = setInterval(refreshStatus, intervalMs);
}

export function stopPolling(): void {
  if (timer !== undefined) {
    clearInterval(timer);
    timer = undefined;
  }
}
