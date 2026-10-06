<script lang="ts">
  import { AudioLines, Radio } from "@lucide/svelte";
  import { playbackState, player } from "../lib/status.svelte";
  import Progress from "./Progress.svelte";

  /** Strip folder prefix and extension for display. */
  function trackLabel(file: string | null): string {
    if (!file) return "Nothing queued";
    const name = file.split("/").pop() ?? file;
    return name.replace(/\.mp3$/i, "");
  }

  // stopped | paused | playing | offline
  let state = $derived(playbackState(player.data));

  let stateLabel = $derived(
    { offline: "Not connected", stopped: "Stopped", paused: "Paused", playing: "Playing" }[
      state
    ],
  );
</script>

<section class="hero">
  <div class="art" aria-hidden="true"><AudioLines size={40} /></div>
  <p class="now-label">Now Streaming</p>
  <h1 class="track">{trackLabel(player.data?.current_file ?? null)}</h1>
  <div class="meta">
    <span class="pill" class:playing={state === "playing"} class:paused={state === "paused"}>
      {stateLabel}
    </span>
    {#if player.data?.selected_device}
      <span class="device"><Radio size={14} /> {player.data.selected_device}</span>
    {/if}
  </div>
  <Progress />
</section>

<style>
  .hero {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 6px;
    padding: 28px 20px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
  }

  .art {
    display: grid;
    place-items: center;
    width: 96px;
    height: 96px;
    border-radius: 50%;
    background: var(--accent-soft);
    color: var(--accent);
    margin-bottom: 8px;
  }

  .now-label {
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--muted);
  }

  .track {
    font-size: 22px;
    font-weight: 700;
    line-height: 1.3;
    max-width: 100%;
    overflow-wrap: anywhere;
  }

  .meta {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 8px;
    flex-wrap: wrap;
    justify-content: center;
  }

  .pill {
    padding: 4px 12px;
    border-radius: 999px;
    font-size: 13px;
    font-weight: 600;
    background: var(--surface-soft);
    border: 1px solid var(--border);
    color: var(--muted);
  }

  .pill.playing {
    color: var(--ok);
    border-color: color-mix(in srgb, var(--ok) 40%, transparent);
  }

  .pill.paused {
    color: var(--warn);
    border-color: color-mix(in srgb, var(--warn) 40%, transparent);
  }

  .device {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 13px;
    color: var(--muted);
  }
</style>
