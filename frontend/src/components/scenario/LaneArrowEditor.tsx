import { MOVEMENTS, type Movement } from "../../scenario/scenarioTypes";
import { sortMovements } from "../../scenario/scenarioModel";
import { GLYPH, MOVE_LABEL } from "./builderOptions";

export function LaneArrowEditor({
  lanes,
  use,
  onChange,
  caption,
}: {
  lanes: number;
  use: Movement[][];
  onChange: (use: Movement[][]) => void;
  caption: string;
}) {
  return (
    <div className="lane-editor" role="group" aria-label={caption}>
      {Array.from({ length: lanes }, (_, i) => {
        const turns = use[i] ?? [];
        return (
          <div key={i} className="lane-card">
            <span className="lane-card-n">Lane {i + 1}</span>
            <span className="lane-card-glyphs" aria-hidden="true">
              {turns.length ? turns.map((t) => GLYPH[t]).join("") : "∅"}
            </span>
            <div className="lane-card-toggles">
              {MOVEMENTS.map((m) => {
                const on = turns.includes(m);
                return (
                  <button
                    key={m}
                    type="button"
                    className={`lane-toggle${on ? " is-on" : ""}`}
                    aria-pressed={on}
                    aria-label={`Lane ${String(i + 1)}: ${MOVE_LABEL[m]}`}
                    title={MOVE_LABEL[m]}
                    onClick={() => {
                      const next = use.map((l) => [...l]);
                      next[i] = sortMovements(
                        on ? turns.filter((t) => t !== m) : [...turns, m],
                      );
                      onChange(next);
                    }}
                  >
                    {GLYPH[m]}
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
