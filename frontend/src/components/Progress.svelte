<script lang="ts">
  import { player } from "../lib/status.svelte";

  // Local clock for smooth 1s/s interpolation between /status polls.
  let now = $state(Date.now());
  setInterval(() => (now = Date.now()), 1000);

  let lastSync = $state({ at: 0, pos: 0, playing: false, track: "" });

  $effect(() => {
    const s = player.data;
    if (!s) return;
    lastSync = {
      at: Date.now(),
      pos: s.stream_position ?? 0,
      playing: !!s.stream_active && !s.is_paused,
      track: s.current_file ?? "",
    };
  });

  let position = $derived.by(() => {
    const duration = player.data?.stream_duration;
    if (duration === null || duration === undefined) return null;
    let p = lastSync.pos;
    if (lastSync.playing) p += (now - lastSync.at) / 1000;
    return Math.min(Math.max(p, 0), duration);
  });

  function format(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${String(s).padStart(2, "0")}`;
  }
</script>

{#if position !== null && player.data?.stream_duration}
  {@const percent = (position / player.data.stream_duration) * 100}
  <div class="progress">
    <div class="bar" role="progressbar" aria-valuenow={Math.round(percent)} aria-valuemin={0} aria-valuemax={100}>
      <div class="fill" style:width={`${percent}%`}></div>
    </div>
    <div class="times">
      <span>{format(position)}</span>
      <span>{format(player.data.stream_duration)}</span>
    </div>
  </div>
{/if}

<style>
  .progress {
    width: 100%;
    max-width: 360px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 10px;
  }

  .bar {
    height: 6px;
    border-radius: 999px;
    background: var(--surface-soft);
    border: 1px solid var(--border);
    overflow: hidden;
  }

  .fill {
    height: 100%;
    border-radius: 999px;
    background: var(--accent);
    transition: width 1s linear;
  }

  .times {
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    font-variant-numeric: tabular-nums;
    color: var(--muted);
  }
</style>
