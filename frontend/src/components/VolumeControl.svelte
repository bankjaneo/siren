<script lang="ts">
  import { Volume1, Volume2, VolumeX } from "@lucide/svelte";
  import { command, isOk } from "../lib/api";
  import { player, refreshStatus } from "../lib/status.svelte";
  import { showError } from "../lib/toast.svelte";

  let volume = $state(5);
  let lastSent = 0;
  let debounce: ReturnType<typeof setTimeout> | undefined;

  // Track the server's volume so external changes (connect, etc.) show up,
  // but don't clobber the slider while the user is dragging it.
  $effect(() => {
    const fromServer = player.data?.current_volume;
    if (fromServer !== undefined && fromServer !== lastSent) {
      volume = fromServer;
    }
  });

  async function send(value: number): Promise<void> {
    if (value < 1 || value > 100) return;
    lastSent = value;
    try {
      const result = await command(`/volume/${value}`);
      if (!isOk(result)) {
        showError(result.message ?? "Failed to set volume");
        lastSent = 0;
      }
      await refreshStatus();
    } catch (error) {
      lastSent = 0;
      showError((error as Error).message);
    }
  }

  function onInput(event: Event): void {
    volume = Number((event.target as HTMLInputElement).value);
    if (debounce !== undefined) clearTimeout(debounce);
    debounce = setTimeout(() => send(volume), 250);
  }
</script>

<div class="volume">
  <span class="icon" aria-hidden="true">
    {#if !player.data?.chromecast_connected}
      <VolumeX size={18} />
    {:else if volume < 50}
      <Volume1 size={18} />
    {:else}
      <Volume2 size={18} />
    {/if}
  </span>
  <input
    type="range"
    min="1"
    max="100"
    bind:value={volume}
    oninput={onInput}
    aria-label="Volume"
    disabled={!player.data?.chromecast_connected}
  />
  <span class="value">{volume}%</span>
</div>

<style>
  .volume {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px 20px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
  }

  .icon {
    display: grid;
    place-items: center;
    color: var(--muted);
  }

  input[type="range"] {
    flex: 1;
    accent-color: var(--accent);
  }

  .value {
    min-width: 42px;
    text-align: right;
    font-variant-numeric: tabular-nums;
    font-weight: 600;
    font-size: 14px;
    color: var(--muted);
  }

  .volume:has(input:disabled) {
    opacity: 0.5;
  }
</style>
