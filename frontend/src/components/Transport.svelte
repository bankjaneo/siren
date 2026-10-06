<script lang="ts">
  import { Pause, Play, SkipBack, SkipForward } from "@lucide/svelte";
  import { command, isOk } from "../lib/api";
  import { player, refreshStatus } from "../lib/status.svelte";
  import { showError } from "../lib/toast.svelte";

  let busy = $state(false);

  // stopped → /play, paused → /resume, playing → /pause
  let mode = $derived.by(() => {
    const s = player.data;
    if (!s || !s.chromecast_connected) return "offline";
    if (!s.stream_active) return "stopped";
    return s.is_paused ? "paused" : "playing";
  });

  async function act(endpoint: string): Promise<void> {
    busy = true;
    try {
      const result = await command(endpoint);
      if (!isOk(result)) showError(result.message ?? "Command failed");
    } catch (error) {
      showError((error as Error).message);
    } finally {
      busy = false;
      await refreshStatus();
    }
  }

  function onToggle(): void {
    if (mode === "playing") act("/pause");
    else if (mode === "paused") act("/resume");
    else if (mode === "stopped") act("/play");
  }
</script>

<div class="transport">
  <button
    class="skip"
    aria-label="Previous track"
    disabled={mode === "offline" || busy}
    onclick={() => act("/previous")}
  >
    <SkipBack size={22} />
  </button>

  <button
    class="main"
    aria-label={mode === "playing" ? "Pause" : "Play"}
    disabled={mode === "offline" || busy}
    onclick={onToggle}
  >
    {#if mode === "playing"}
      <Pause size={30} />
    {:else}
      <Play size={30} />
    {/if}
  </button>

  <button
    class="skip"
    aria-label="Next track"
    disabled={mode === "offline" || busy}
    onclick={() => act("/next")}
  >
    <SkipForward size={22} />
  </button>
</div>

<style>
  .transport {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 22px;
  }

  .skip {
    display: grid;
    place-items: center;
    width: 56px;
    height: 56px;
    border-radius: 50%;
    background: var(--surface);
    border: 1px solid var(--border);
    box-shadow: var(--shadow);
    transition: transform 0.15s ease;
  }

  .skip:hover:not(:disabled) {
    transform: scale(1.06);
  }

  .main {
    display: grid;
    place-items: center;
    width: 76px;
    height: 76px;
    border-radius: 50%;
    background: var(--accent);
    color: var(--accent-text);
    box-shadow: var(--shadow);
    transition: transform 0.15s ease;
  }

  .main:hover:not(:disabled) {
    transform: scale(1.05);
  }

  button:disabled {
    opacity: 0.45;
  }
</style>
