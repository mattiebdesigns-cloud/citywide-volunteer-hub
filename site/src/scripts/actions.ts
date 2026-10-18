// Heart (save on this device), share, and "Add to my calendar".
// Buttons are found by data attributes, so pv-design's components can carry them:
//   data-save-id="<listing id>"             heart; aria-pressed shows the state
//   data-share-url="<path>" data-share-title  share a plain link to the listing
//   data-ics="<calendar file text>" data-ics-name="<file name>"
// Messages ("Link copied.") come from data attributes on #action-status,
// which the page fills from the translation files.
import { readSaved, writeSaved } from "./device.ts";

export const SAVED_CHANGED = "cvh:saved-changed";

const status = document.getElementById("action-status");
let statusTimer: number | undefined;

function announce(key: "copied" | "failed"): void {
  if (!status) return;
  status.textContent = status.dataset[key] ?? "";
  window.clearTimeout(statusTimer);
  statusTimer = window.setTimeout(() => (status.textContent = ""), 5000);
}

function wireSave(): void {
  const saved = readSaved();
  for (const button of document.querySelectorAll<HTMLButtonElement>("[data-save-id]")) {
    const id = button.dataset.saveId ?? "";
    button.setAttribute("aria-pressed", String(saved.has(id)));
    button.addEventListener("click", () => {
      const now = readSaved();
      if (now.has(id)) now.delete(id);
      else now.add(id);
      writeSaved(now);
      for (const same of document.querySelectorAll<HTMLButtonElement>(`[data-save-id="${CSS.escape(id)}"]`)) {
        same.setAttribute("aria-pressed", String(now.has(id)));
      }
      document.dispatchEvent(new CustomEvent(SAVED_CHANGED));
    });
  }
}

function wireShare(): void {
  for (const button of document.querySelectorAll<HTMLButtonElement>("[data-share-url]")) {
    button.addEventListener("click", async () => {
      const url = new URL(button.dataset.shareUrl ?? "", location.href).href;
      if (navigator.share) {
        try {
          await navigator.share({ title: button.dataset.shareTitle, url });
          return;
        } catch (error) {
          if ((error as DOMException)?.name === "AbortError") return; // the visitor closed the share sheet
        }
      }
      try {
        await navigator.clipboard.writeText(url);
        announce("copied");
      } catch {
        announce("failed");
      }
    });
  }
}

function wireIcs(): void {
  for (const button of document.querySelectorAll<HTMLButtonElement>("[data-ics]")) {
    button.hidden = false;
    button.addEventListener("click", () => {
      // Made in the browser: no request reaches any server.
      const blob = new Blob([button.dataset.ics ?? ""], { type: "text/calendar;charset=utf-8" });
      const href = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = href;
      link.download = button.dataset.icsName ?? "shift.ics";
      document.body.append(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(href), 10_000);
    });
  }
}

wireSave();
wireShare();
wireIcs();
