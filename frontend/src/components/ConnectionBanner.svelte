<script lang="ts">
  import { player } from "../lib/status.svelte";
</script>

{#if player.data?.connection_lost}
  <div class="banner" role="status">
    <span class="spinner" aria-hidden="true"></span>
    Reconnecting to speaker…
  </div>
{/if}

<style>
  .banner {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    padding: 10px 16px;
    border-radius: 12px;
    background: var(--accent-soft);
    color: var(--warn);
    font-weight: 600;
    font-size: 14px;
  }

  .spinner {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    border: 2px solid var(--warn);
    border-top-color: transparent;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
