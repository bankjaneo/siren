<script lang="ts">
  import { Play } from "@lucide/svelte";
  import { command, getFiles, isOk } from "../lib/api";
  import { player, refreshStatus } from "../lib/status.svelte";
  import { showError } from "../lib/toast.svelte";

  let files = $state<string[]>([]);
  let loading = $state(true);
  let jumping = $state<number | null>(null);

  /** Track name without folder prefix / extension. */
  function label(file: string): string {
    return file.replace(/\.mp3$/i, "");
  }

  async function load(): Promise<void> {
    loading = true;
    try {
      const result = await getFiles();
      files = result.files;
    } catch (error) {
      showError((error as Error).message);
      files = [];
    } finally {
      loading = false;
    }
  }

  async function jump(index: number): Promise<void> {
    jumping = index;
    try {
      const result = await command(`/play-file/${index}`);
      if (!isOk(result)) showError(result.message ?? "Failed to play file");
      await refreshStatus();
    } catch (error) {
      showError((error as Error).message);
    } finally {
      jumping = null;
    }
  }

  load();
</script>

<div class="file-list">
  {#if loading}
    <p class="hint">Loading files…</p>
  {:else if files.length === 0}
    <p class="hint">No MP3 files in the music folder</p>
  {:else}
    {#each files as file, index (file)}
      <button
        class="file"
        class:current={player.data?.stream_active && player.data?.current_file_index === index}
        disabled={!player.data?.chromecast_connected || jumping !== null}
        onclick={() => jump(index)}
      >
        <span class="num">{index + 1}</span>
        <span class="name">{label(file)}</span>
        {#if jumping === index}
          <span class="jumping">…</span>
        {:else if player.data?.stream_active && player.data?.current_file_index === index}
          <span class="marker" aria-hidden="true"><Play size={14} /></span>
        {/if}
      </button>
    {/each}
  {/if}
</div>

<style>
  .file-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
    max-height: 320px;
    overflow-y: auto;
  }

  .hint {
    color: var(--muted);
    font-size: 14px;
    padding: 8px 2px;
  }

  .file {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 12px;
    border-radius: 10px;
    text-align: left;
    font-size: 14px;
    background: var(--surface-soft);
    border: 1px solid transparent;
    transition: border-color 0.15s ease;
  }

  .file:hover:not(:disabled) {
    border-color: var(--border);
  }

  .file:disabled {
    opacity: 0.5;
  }

  .file.current {
    border-color: color-mix(in srgb, var(--accent) 50%, transparent);
    background: var(--accent-soft);
  }

  .num {
    color: var(--muted);
    font-variant-numeric: tabular-nums;
    min-width: 1.5em;
  }

  .name {
    flex: 1;
    overflow-wrap: anywhere;
  }

  .marker {
    display: grid;
    place-items: center;
    color: var(--accent);
  }

  .jumping {
    color: var(--muted);
  }
</style>
