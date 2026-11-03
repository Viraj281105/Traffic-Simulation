/** How far two strategies' served populations differ, as the study API
 *  reports it on each paired delay comparison (metric contract 7.10a). */
export interface ServedDemand {
  admittedShareOfNominalDifference: number | null;
  unfinishedShareDifference: number | null;
  /** False when either share differs by more than 5 points. */
  comparable: boolean;
  /** The strategy with the lower mean delay admitted less of the demand,
   *  or left more of it unfinished, by more than 5 points. */
  lowerDelayServedLess: boolean;
  /** Mean wait before entry, first minus second (s); absent in results
   *  saved before it. Delay is measured from entry, over the same vehicles. */
  averageEntryWaitDifference?: number | null;
  /** Adding the wait to enter reverses which side has the lower delay. */
  entryWaitReversesDelay?: boolean;
}

/** A caution for a delay reading, or null when there is nothing to add.
 *  Mean delay averages only vehicles that finished, so a lower delay that
 *  came with less traffic served may reflect that rather than better
 *  control. It is a caution, not a verdict: the shares are means over
 *  seeds and say nothing about cause. */
export function servedDemandNote(
  served: ServedDemand | undefined,
): string | null {
  const notes: string[] = [];
  if (served?.lowerDelayServedLess)
    notes.push(
      "The lower-delay side served less of the demand (admitted less or left more unfinished); that may explain part of the difference.",
    );
  if (served?.entryWaitReversesDelay)
    notes.push(
      "Counting the wait to enter as well, the order reverses: the lower-delay side's vehicles waited longer outside the map.",
    );
  return notes.length ? notes.join(" ") : null;
}
