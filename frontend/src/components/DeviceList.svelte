<script lang="ts">
  import { Check, Speaker } from "@lucide/svelte";
  import { command, getDevices, isOk, type CastDevice } from "../lib/api";
  import { player, refreshStatus } from "../lib/status.svelte";
  import { showError } from "../lib/toast.svelte";

  let devices = $state<CastDevice[]>([]);
  let loading = $state(true);
  let connecting = $state<string | null>(null);

  async function load(): Promise<void> {
    loading = true;
    try {
      const result = await getDevices();
      if (result.error) {
        showError(result.error);
        devices = [];
      } else {
        devices = result.devices;
      }
    } catch (error) {
      showError((error as Error).message);
      devices = [];
    } finally {
      loading = false;
    }
  }

  async function connect(name: string): Promise<void> {
    connecting = name;
    try {
      const result = await command(`/connect/${encodeURIComponent(name)}`);
      if (!isOk(result)) {
        showError(result.message ?? "Failed to connect");
      } else {
        await refreshStatus();
        // Auto-play if nothing is streaming on the newly connected speaker.
        if (!player.data?.stream_active) {
          const play = await command("/play");
          if (!isOk(play)) showError(play.message ?? "Failed to start playback");
          await refreshStatus();
        }
      }
    } catch (error) {
      showError((error as Error).message);
    } finally {
      connecting = null;
      await load();
    }
  }

  load();
</script>

<div class="device-list">
  {#if loading}
    <p class="hint">Scanning for devices…</p>
  {:else if devices.length === 0}
    <p class="hint">No devices found</p>
  {:else}
    {#each devices as device (device.name)}
      <div class="device">
        <Speaker size={20} class="icon" aria-hidden="true" />
        <div class="info">
          <span class="name">
            {device.name}
            {#if player.data?.selected_device === device.name}
              <span class="connected-badge"><Check size={12} /> Connected</span>
            {/if}
          </span>
          <span class="model">{device.model}</span>
        </div>
        <button
          class="connect"
          disabled={connecting !== null || player.data?.selected_device === device.name}
          onclick={() => connect(device.name)}
        >
          {connecting === device.name ? "Connecting…" : "Connect"}
        </button>
      </div>
    {/each}
  {/if}
</div>

<style>
  .device-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .hint {
    color: var(--muted);
    font-size: 14px;
    padding: 8px 2px;
  }

  .device {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 12px 14px;
    border-radius: 12px;
    background: var(--surface-soft);
    border: 1px solid var(--border);
  }

  .device :global(.icon) {
    flex-shrink: 0;
    color: var(--muted);
  }

  .info {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .name {
    font-weight: 600;
    font-size: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .connected-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    font-weight: 700;
    color: var(--ok);
    border: 1px solid color-mix(in srgb, var(--ok) 40%, transparent);
    border-radius: 999px;
    padding: 1px 8px;
  }

  .model {
    font-size: 12px;
    color: var(--muted);
  }

  .connect {
    padding: 8px 16px;
    border-radius: 999px;
    background: var(--accent);
    color: var(--accent-text);
    font-size: 13px;
    font-weight: 600;
    white-space: nowrap;
  }

  .connect:disabled {
    opacity: 0.5;
  }
</style>
