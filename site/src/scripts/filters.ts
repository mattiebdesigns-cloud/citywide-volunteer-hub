// The filter panel on the home page (PROJECT.md 2). Browser only: nothing
// here sends a request. See components/FilterPanel.astro.
import { EMPTY_FILTERS, activeCount, matches, type CardFacts, type FilterState } from "../lib/filter-logic.ts";
import { localParts } from "../lib/time.ts";
import { readFilters, readSaved, writeFilters } from "./device.ts";

const panel = document.getElementById("filter-panel");
const toggle = document.getElementById("filters-toggle") as HTMLButtonElement | null;
const list = document.getElementById("listing-list");
const countEl = document.getElementById("results-count");
const noneEl = document.getElementById("results-none");

if (panel && toggle && list && countEl) {
  const timeZone = panel.dataset.timezone ?? "UTC";
  const items = [...list.querySelectorAll<HTMLElement>("li[data-id]")];
  const cards = items.map((li): [HTMLElement, CardFacts] => {
    const d = li.dataset;
    return [
      li,
      {
        id: d.id ?? "",
        date: d.date ?? "",
        weekday: Number(d.weekday),
        time: d.time ?? "",
        area: d.area ?? "",
        cause: d.cause ?? "",
        type: d.type ?? "",
        join: d.join ?? "",
        training: d.training ?? "",
        spanish: d.spanish ?? "",
        host: d.host ?? "",
        faith: d.faith ?? "",
        activities: (d.activity ?? "").split(" ").filter(Boolean),
      },
    ];
  });
  const overAt = new Map(items.map((li) => [li, Number(li.dataset.overAt)]));

  const selects = [...panel.querySelectorAll<HTMLSelectElement | HTMLInputElement>("[data-filter]")];
  const chips = [...panel.querySelectorAll<HTMLButtonElement>("[data-filter-toggle]")];
  const dateField = panel.querySelector<HTMLElement>("[data-date-field]");
  const countBadge = toggle.querySelector<HTMLElement>("[data-filters-count]");
  const pluralRules = new Intl.PluralRules(document.documentElement.lang);

  let state: FilterState = readFilters(EMPTY_FILTERS);

  function showState(): void {
    for (const field of selects) {
      const key = field.dataset.filter as keyof FilterState;
      const value = String(state[key] ?? "");
      // A saved choice that no longer exists (the listing went away) falls back to "any".
      field.value = value;
      if (field.value !== value) {
        field.value = "";
        (state as unknown as Record<string, unknown>)[key] = "";
      }
    }
    for (const chip of chips) {
      const key = chip.dataset.filterToggle as keyof FilterState;
      chip.setAttribute("aria-pressed", String(Boolean(state[key])));
    }
    if (dateField) dateField.hidden = state.day !== "pick_date";
  }

  function plural(el: HTMLElement, count: number): string {
    const text = el.dataset[`count${pluralRules.select(count) === "one" ? "One" : "Other"}`] ?? "";
    return text.replace("{count}", new Intl.NumberFormat(document.documentElement.lang).format(count));
  }

  function apply(): void {
    const today = localParts(Date.now(), timeZone).date;
    const saved = readSaved();
    const now = Date.now();
    let shown = 0;
    for (const [li, facts] of cards) {
      const over = (overAt.get(li) ?? Infinity) < now; // built yesterday, already over today
      const visible = !over && matches(facts, state, today, saved);
      li.hidden = !visible;
      if (visible) shown += 1;
    }
    countEl!.textContent = plural(countEl!, shown);
    if (noneEl) noneEl.hidden = shown > 0;
    const active = activeCount(state);
    if (countBadge) {
      // Sighted people see the number in a badge; screen readers hear ", 2 filters on".
      countBadge.hidden = active === 0;
      const number = countBadge.querySelector<HTMLElement>("[data-filters-number]");
      const words = countBadge.querySelector<HTMLElement>("[data-filters-words]");
      if (number) number.textContent = active ? new Intl.NumberFormat(document.documentElement.lang).format(active) : "";
      if (words) words.textContent = active ? `, ${plural(countBadge, active)}` : "";
    }
    writeFilters(state);
  }

  function open(isOpen: boolean, returnFocus = true): void {
    panel!.hidden = !isOpen;
    toggle!.setAttribute("aria-expanded", String(isOpen));
    if (isOpen) panel!.querySelector<HTMLElement>("select, input, button")?.focus();
    else if (returnFocus) toggle!.focus();
  }

  for (const field of selects) {
    field.addEventListener("change", () => {
      (state as unknown as Record<string, unknown>)[field.dataset.filter!] = field.value;
      if (field.dataset.filter === "day" && field.value !== "pick_date") state.date = "";
      showState();
      apply();
    });
  }
  for (const chip of chips) {
    chip.addEventListener("click", () => {
      const key = chip.dataset.filterToggle as "no_training" | "spanish" | "saved";
      state[key] = !state[key];
      showState();
      apply();
    });
  }
  panel.querySelector("[data-filters-apply]")?.addEventListener("click", () => {
    open(false, false);
    document.getElementById("results-heading")?.focus();
  });
  panel.querySelector("[data-filters-clear]")?.addEventListener("click", () => {
    state = { ...EMPTY_FILTERS };
    showState();
    apply();
  });
  panel.querySelector("[data-filters-close]")?.addEventListener("click", () => open(false));
  panel.addEventListener("keydown", (event) => {
    if (event.key === "Escape") open(false);
  });
  toggle.addEventListener("click", () => open(panel.hidden));
  // A heart tapped while "Only shifts I saved" is on does not hide its card
  // at once, so keyboard focus is not lost; the list updates on the next change.

  toggle.hidden = false;
  showState();
  apply();
}
