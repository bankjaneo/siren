/** Theme preference (system / light / dark), persisted in localStorage. */

export type Theme = "system" | "light" | "dark";

const STORAGE_KEY = "siren-theme";

export const theme = $state<{ current: Theme }>({
  current: (localStorage.getItem(STORAGE_KEY) as Theme | null) ?? "system",
});

function apply(value: Theme): void {
  if (value === "system") {
    delete document.documentElement.dataset.theme;
  } else {
    document.documentElement.dataset.theme = value;
  }
}

/** Advance system → light → dark → system. */
export function cycleTheme(): void {
  const order: Theme[] = ["system", "light", "dark"];
  theme.current = order[(order.indexOf(theme.current) + 1) % order.length];
  localStorage.setItem(STORAGE_KEY, theme.current);
  apply(theme.current);
}
