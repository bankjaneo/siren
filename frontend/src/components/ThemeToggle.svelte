<script lang="ts">
  import { Moon, Sun, Monitor } from "@lucide/svelte";
  import { cycleTheme, theme, type Theme } from "../lib/theme.svelte";

  const labels: Record<Theme, string> = {
    system: "System theme",
    light: "Light theme",
    dark: "Dark theme",
  };
</script>

<button
  class="theme-toggle"
  onclick={cycleTheme}
  title={labels[theme.current]}
  aria-label={labels[theme.current]}
>
  {#if theme.current === "system"}
    <Monitor size={18} />
  {:else if theme.current === "light"}
    <Sun size={18} />
  {:else}
    <Moon size={18} />
  {/if}
</button>

<style>
  .theme-toggle {
    display: grid;
    place-items: center;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: var(--surface);
    border: 1px solid var(--border);
    box-shadow: var(--shadow);
    color: var(--muted);
    transition: transform 0.15s ease;
  }

  .theme-toggle:hover {
    transform: scale(1.06);
    color: var(--text);
  }
</style>
