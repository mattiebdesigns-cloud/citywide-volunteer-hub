// Filters on the Flexible opportunities page (decision 0018). Browser only:
// nothing here sends a request. See components/FlexibleFilterPanel.astro.
import {
  EMPTY_FLEXIBLE_FILTERS,
  flexibleActiveCount,
  flexibleMatches,
  type FlexibleFacts,
  type FlexibleFilterState,
} from "../lib/filter-logic.ts";
import { FLEXIBLE_FILTERS_KEY, readFilters, writeFilters } from "./device.ts";

const panel = document.getElementById("filter-panel");
const toggle = document.getElementById("filters-toggle") as HTMLButtonElement | null;
const list = document.getElementById("listing-list");
const countEl = document.getElementById("results-count");
const noneEl = document.getElementById("results-none");

if (panel && toggle && list && countEl) {
  const cards = [...list.querySelectorAll<HTMLElement>("li[data-id]")].map((li): [HTMLElement, FlexibleFacts] => [
    li,
    { section: li.dataset.section ?? "", cause: li.dataset.cause ?? "", join: li.dataset.join ?? "" },
  ]);
  const selects = [...panel.querySelectorAll<HTMLSelectElement>("select[data-filter]")];
  const countBadge = toggle.querySelector<HTMLElement>("[data-filters-count]");
  const lang = document.documentElement.lang;
  const pluralRules = new Intl.PluralRules(lang);
  const number = new Intl.NumberFormat(lang);

  let state: FlexibleFilterState = readFilters(EMPTY_FLEXIBLE_FILTERS, FLEXIBLE_FILTERS_KEY);

  function showState(): void {
    for (const field of selects) {
      const key = field.dataset.filter as keyof FlexibleFilterState;
      const value = String(state[key] ?? "");
      field.value = value;
      // A saved choice that no longer exists falls back to "any".
      if (field.value !== value) {
        field.value = "";
        state[key] = "";
      }
    }
  }

  function plural(el: HTMLElement, count: number): string {
    const text = el.dataset[`count${pluralRules.select(count) === "one" ? "One" : "Other"}`] ?? "";
    return text.replace("{count}", number.format(count));
  }

  function apply(): void {
    let shown = 0;
    for (const [li, facts] of cards) {
      const visible = flexibleMatches(facts, state);
      li.hidden = !visible;
      if (visible) shown += 1;
    }
    countEl!.textContent = plural(countEl!, shown);
    if (noneEl) noneEl.hidden = shown > 0;
    const active = flexibleActiveCount(state);
    if (countBadge) {
      countBadge.hidden = active === 0;
      const num = countBadge.querySelector<HTMLElement>("[data-filters-number]");
      const words = countBadge.querySelector<HTMLElement>("[data-filters-words]");
      if (num) num.textContent = active ? number.format(active) : "";
      if (words) words.textContent = active ? `, ${plural(countBadge, active)}` : "";
    }
    writeFilters(state, FLEXIBLE_FILTERS_KEY);
  }

  function open(isOpen: boolean, returnFocus = true): void {
    panel!.hidden = !isOpen;
    toggle!.setAttribute("aria-expanded", String(isOpen));
    if (isOpen) panel!.querySelector<HTMLElement>("select, button")?.focus();
    else if (returnFocus) toggle!.focus();
  }

  for (const field of selects) {
    field.addEventListener("change", () => {
      state[field.dataset.filter as keyof FlexibleFilterState] = field.value;
      apply();
    });
  }
  panel.querySelector("[data-filters-apply]")?.addEventListener("click", () => {
    open(false, false);
    document.getElementById("results-heading")?.focus();
  });
  panel.querySelector("[data-filters-clear]")?.addEventListener("click", () => {
    state = { ...EMPTY_FLEXIBLE_FILTERS };
    showState();
    apply();
  });
  panel.querySelector("[data-filters-close]")?.addEventListener("click", () => open(false));
  panel.addEventListener("keydown", (event) => {
    if (event.key === "Escape") open(false);
  });
  toggle.addEventListener("click", () => open(panel.hidden));

  toggle.hidden = false;
  showState();
  apply();
}
