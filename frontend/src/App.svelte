<script lang="ts">
  import { onMount } from "svelte";
  import ConnectionBanner from "./components/ConnectionBanner.svelte";
  import DeviceList from "./components/DeviceList.svelte";
  import FileList from "./components/FileList.svelte";
  import NowPlaying from "./components/NowPlaying.svelte";
  import ThemeToggle from "./components/ThemeToggle.svelte";
  import Transport from "./components/Transport.svelte";
  import VolumeControl from "./components/VolumeControl.svelte";
  import { startPolling } from "./lib/status.svelte";
  import { toast } from "./lib/toast.svelte";

  let tab = $state<"devices" | "files">("devices");

  onMount(() => startPolling());
</script>

<div class="shell">
  <header>
    <span class="brand">📣 Siren</span>
    <ThemeToggle />
  </header>

  <main>
    <ConnectionBanner />
    <NowPlaying />
    <Transport />
    <VolumeControl />

    <div class="tabs" role="tablist">
      <button
        role="tab"
        aria-selected={tab === "devices"}
        class:active={tab === "devices"}
        onclick={() => (tab = "devices")}
      >
        Devices
      </button>
      <button
        role="tab"
        aria-selected={tab === "files"}
        class:active={tab === "files"}
        onclick={() => (tab = "files")}
      >
        Files
      </button>
    </div>

    {#if tab === "devices"}
      <DeviceList />
    {:else}
      <FileList />
    {/if}
  </main>

  {#if toast.message}
    <div class="toast" role="alert">{toast.message}</div>
  {/if}
</div>

<style>
  .shell {
    max-width: 560px;
    margin: 0 auto;
    padding: 20px 16px 48px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .brand {
    font-size: 20px;
    font-weight: 800;
    letter-spacing: -0.01em;
  }

  main {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .tabs {
    display: flex;
    gap: 8px;
    margin-top: 8px;
  }

  .tabs button {
    flex: 1;
    padding: 10px 0;
    border-radius: 999px;
    font-size: 14px;
    font-weight: 600;
    color: var(--muted);
    background: var(--surface);
    border: 1px solid var(--border);
  }

  .tabs button.active {
    color: var(--accent-text);
    background: var(--accent);
    border-color: var(--accent);
  }

  .toast {
    position: fixed;
    left: 50%;
    bottom: 24px;
    transform: translateX(-50%);
    max-width: min(90vw, 480px);
    padding: 12px 18px;
    border-radius: 12px;
    background: var(--danger);
    color: #fff;
    font-size: 14px;
    font-weight: 500;
    box-shadow: var(--shadow);
  }

  @media (min-width: 720px) {
    .shell {
      padding-top: 40px;
    }
  }
</style>
