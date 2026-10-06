/** Theme preference (system / light / dark), persisted in localStorage. */

export type Theme = "system" | "light" | "dark";

const STORAGE_KEY = "siren-theme";

export const theme = $state<{ current: Theme }>({
  current: (localStorage.getItem(STORAGE_KEY) as Theme | null) ?? "system",
});

const prefersDark = window.matchMedia("(prefers-color-scheme: dark)");

/** Resolve a preference to a concrete theme ("system" follows the OS). */
function resolve(value: Theme): "light" | "dark" {
  if (value !== "system") return value;
  return prefersDark.matches ? "dark" : "light";
}

function apply(value: Theme): void {
  document.documentElement.dataset.theme = resolve(value);
}

// Follow OS theme changes while on the "system" preference.
prefersDark.addEventListener("change", () => {
  if (theme.current === "system") apply("system");
});

/** Advance system → light → dark → system. */
export function cycleTheme(): void {
  const order: Theme[] = ["system", "light", "dark"];
  theme.current = order[(order.indexOf(theme.current) + 1) % order.length];
  localStorage.setItem(STORAGE_KEY, theme.current);
  apply(theme.current);
}
