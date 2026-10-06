/** Tiny transient-error toast state. */

export const toast = $state<{ message: string | null }>({ message: null });

let hideTimer: ReturnType<typeof setTimeout> | undefined;

/** Show an error message for a few seconds. */
export function showError(message: string): void {
  toast.message = message;
  if (hideTimer !== undefined) clearTimeout(hideTimer);
  hideTimer = setTimeout(() => {
    toast.message = null;
  }, 5000);
}
