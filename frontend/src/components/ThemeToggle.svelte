<script lang="ts">
  import { cycleTheme, theme, type Theme } from "../lib/theme.svelte";

  const icons: Record<Theme, string> = {
    system: "🖥️",
    light: "☀️",
    dark: "🌙",
  };

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
  {icons[theme.current]}
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
    font-size: 16px;
    transition: transform 0.15s ease;
  }

  .theme-toggle:hover {
    transform: scale(1.06);
  }
</style>
