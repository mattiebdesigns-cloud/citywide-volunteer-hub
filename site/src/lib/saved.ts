// Saved shifts (hearts) are cleared from the device once the shift is over
// (owner, Q32). Pure, so it can be tested without a browser.

/**
 * The saved ids to keep: those still in this build whose listing has not
 * ended. `live` maps each listing id in the build to when it is over
 * (milliseconds). Ids not in the build are dropped too: the listing ended,
 * was removed, or was never ours.
 */
export function pruneSaved(saved: Iterable<string>, live: ReadonlyMap<string, number>, now: number): Set<string> {
  const keep = new Set<string>();
  for (const id of saved) {
    const overAt = live.get(id);
    if (overAt !== undefined && overAt >= now) keep.add(id);
  }
  return keep;
}
