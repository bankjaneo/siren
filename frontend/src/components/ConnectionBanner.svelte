<script lang="ts">
  import { LoaderCircle } from "@lucide/svelte";
  import { player } from "../lib/status.svelte";
</script>

{#if player.data?.connection_lost}
  <div class="banner" role="status">
    <LoaderCircle class="spinner" size={16} aria-hidden="true" />
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

  .banner :global(.spinner) {
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
