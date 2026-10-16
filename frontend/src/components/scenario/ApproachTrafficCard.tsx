import {
  MOVEMENTS,
  type ApproachName,
  type ApproachSpec,
  type Movement,
} from "../../scenario/scenarioTypes";
import {
  signalLaneUse,
  turningShare,
  turningTotal,
  type LocalIssue,
} from "../../scenario/scenarioModel";
import { MixEditor } from "./MixEditor";
import { BUSY_LEVELS, GLYPH, MOVE_LABEL, cap } from "./builderOptions";

export function ApproachTrafficCard({
  approach,
  arm,
  possible,
  selected,
  onSelect,
  onChange,
  issues,
}: {
  approach: ApproachName;
  arm: ApproachSpec;
  /** Movements that lead to a road that exists (V1.5). */
  possible: Movement[];
  selected: boolean;
  onSelect: () => void;
  onChange: (change: Partial<ApproachSpec>) => void;
  issues: LocalIssue[];
}) {
  const level = BUSY_LEVELS.find(
    (l) => Math.abs(l.perLane * arm.lanes - arm.vehiclesPerHour) < 1,
  );
  const turning = turningTotal(arm.turning);
  return (
    <div
      className={`approach-card${selected ? " is-selected" : ""}${issues.length ? " has-issues" : ""}`}
      onFocusCapture={onSelect}
      onClick={onSelect}
    >
      <div className="approach-card-head">
        <h4>{cap(approach)}</h4>
        <span className="sb-muted sb-small">
          {arm.lanes} lane{arm.lanes === 1 ? "" : "s"}
        </span>
      </div>
      <div className="chip-row">
        {BUSY_LEVELS.map((l) => (
          <button
            key={l.id}
            type="button"
            className={`chip${level?.id === l.id ? " is-active" : ""}`}
            aria-pressed={level?.id === l.id}
            onClick={() => {
              onChange({ vehiclesPerHour: l.perLane * arm.lanes });
            }}
          >
            {l.label}
          </button>
        ))}
      </div>
      <div className="sb-inline sb-small">
        <label>
          <input
            type="number"
            min={0}
            max={7200}
            step={10}
            value={Math.round(arm.vehiclesPerHour)}
            aria-label={`${approach} vehicles per hour`}
            onChange={(e) => {
              if (e.target.value !== "")
                onChange({
                  vehiclesPerHour: Math.max(0, Number(e.target.value)),
                });
            }}
          />{" "}
          vehicles / hour
        </label>
        <span className="sb-muted">
          ≈ {Math.round(arm.vehiclesPerHour / arm.lanes)} per lane
        </span>
      </div>
      <div className="sb-subhead">
        <span>Where do drivers go?</span>
        <span className={Math.abs(turning - 1) <= 0.01 ? "sb-ok" : "sb-bad"}>
          {Math.round(turning * 100)}%
        </span>
      </div>
      <div className="turning-row">
        {MOVEMENTS.filter(
          // A U-turn share is offered once a lane allows U-turns (or the
          // road already has one), so the guided view stays simple.
          (m) =>
            (m !== "uturn" ||
              turningShare(arm.turning, m) > 0 ||
              signalLaneUse(arm).some((l) => l.includes("uturn")) ||
              (arm.roundaboutLaneUse ?? []).some((l) => l.includes("uturn"))) &&
            (possible.includes(m) || turningShare(arm.turning, m) > 0),
        ).map((m) => (
          <label key={m} className="turning-field">
            <span>
              {GLYPH[m]} {MOVE_LABEL[m]}
            </span>
            <input
              type="number"
              min={0}
              max={100}
              step={5}
              value={Math.round(turningShare(arm.turning, m) * 1000) / 10}
              aria-label={`${approach}: share turning ${m} (%)`}
              onChange={(e) => {
                if (e.target.value === "") return;
                onChange({
                  turning: {
                    ...arm.turning,
                    [m]:
                      Math.max(0, Math.min(100, Number(e.target.value))) / 100,
                  },
                });
              }}
            />
          </label>
        ))}
      </div>
      <details className="sb-own-mix" open={!!arm.vehicleMix}>
        <summary>Own vehicle mix for this road</summary>
        {arm.vehicleMix ? (
          <>
            <MixEditor
              value={arm.vehicleMix}
              allowCarsOnlyNull={false}
              label={`${cap(approach)} mix`}
              onChange={(mix) => {
                onChange({ vehicleMix: mix });
              }}
            />
            <button
              type="button"
              className="link-btn"
              onClick={() => {
                onChange({ vehicleMix: null });
              }}
            >
              Use the junction’s mix
            </button>
          </>
        ) : (
          <button
            type="button"
            className="link-btn"
            onClick={() => {
              onChange({
                vehicleMix: {
                  car: 0.7,
                  suv: 0.1,
                  bus: 0.1,
                  truck: 0.05,
                  motorcycle: 0.05,
                },
              });
            }}
          >
            Give this road its own mix
          </button>
        )}
      </details>
      {issues.map((i) => (
        <p key={i.message} className="q-note is-caution sb-small">
          {i.message}
        </p>
      ))}
    </div>
  );
}
