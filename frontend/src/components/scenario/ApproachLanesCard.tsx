import { useState } from "react";
import {
  OPPOSITE,
  type ApproachName,
  type ApproachSpec,
  type Movement,
} from "../../scenario/scenarioTypes";
import {
  defaultLaneUse,
  signalLaneUse,
  withLaneCount,
  type LocalIssue,
} from "../../scenario/scenarioModel";
import { GLYPH, cap } from "./builderOptions";
import { Stepper } from "./fields";
import { LaneArrowEditor } from "./LaneArrowEditor";

export function ApproachLanesCard({
  approach,
  arm,
  hasOpposite,
  possible,
  selected,
  onSelect,
  onChange,
  onCopyOpposite,
  roundaboutUse,
  issues,
}: {
  approach: ApproachName;
  arm: ApproachSpec;
  hasOpposite: boolean;
  /** Movements that lead to a road that exists (V1.5). */
  possible: Movement[];
  selected: boolean;
  onSelect: () => void;
  onChange: (change: Partial<ApproachSpec>) => void;
  onCopyOpposite: () => void;
  roundaboutUse?: Movement[][];
  issues: LocalIssue[];
}) {
  const [editRoundabout, setEditRoundabout] = useState(!!arm.roundaboutLaneUse);
  const signalUse = signalLaneUse(arm, possible);
  return (
    <div
      className={`approach-card${selected ? " is-selected" : ""}${issues.length ? " has-issues" : ""}`}
      onFocusCapture={onSelect}
      onClick={onSelect}
    >
      <div className="approach-card-head">
        <h4>{cap(approach)}</h4>
        <Stepper
          label="Lanes"
          value={arm.lanes}
          min={1}
          max={4}
          onChange={(lanes) => {
            onChange(withLaneCount(arm, lanes));
          }}
        />
      </div>
      <div className="sb-inline sb-small">
        <label>
          Length{" "}
          <input
            type="number"
            min={60}
            max={1000}
            step={10}
            value={arm.length}
            aria-label={`${approach} approach length (m)`}
            onChange={(e) => {
              if (e.target.value !== "")
                onChange({ length: Number(e.target.value) });
            }}
          />{" "}
          m
        </label>
        {hasOpposite && (
          <button type="button" className="link-btn" onClick={onCopyOpposite}>
            Same as {OPPOSITE[approach]}
          </button>
        )}
      </div>
      <div className="sb-subhead">
        <span>Signal lane arrows</span>
        {arm.laneUse ? (
          <button
            type="button"
            className="link-btn"
            onClick={() => {
              onChange({ laneUse: null });
            }}
          >
            Use default arrows
          </button>
        ) : (
          <span className="sb-muted">default</span>
        )}
      </div>
      <LaneArrowEditor
        lanes={arm.lanes}
        use={signalUse}
        caption={`${approach} signal lane arrows`}
        onChange={(use) => {
          onChange({ laneUse: use });
        }}
      />
      <div className="sb-subhead">
        <span>Roundabout lane markings</span>
        <button
          type="button"
          className="link-btn"
          onClick={() => {
            if (editRoundabout) onChange({ roundaboutLaneUse: null });
            else
              onChange({
                roundaboutLaneUse:
                  roundaboutUse && roundaboutUse.length === arm.lanes
                    ? roundaboutUse.map((l) => [...l])
                    : defaultLaneUse(arm.lanes),
              });
            setEditRoundabout(!editRoundabout);
          }}
        >
          {editRoundabout ? "Make automatic" : "Edit"}
        </button>
      </div>
      {editRoundabout && arm.roundaboutLaneUse ? (
        <LaneArrowEditor
          lanes={arm.lanes}
          use={arm.roundaboutLaneUse}
          caption={`${approach} roundabout lane markings`}
          onChange={(use) => {
            onChange({ roundaboutLaneUse: use });
          }}
        />
      ) : (
        <p className="sb-muted sb-small">
          Automatic
          {roundaboutUse
            ? `: ${roundaboutUse.map((l, i) => `lane ${String(i + 1)} ${l.map((t) => GLYPH[t]).join("")}`).join(", ")}`
            : ""}
        </p>
      )}
      {issues.map((i) => (
        <p key={i.message} className="q-note is-caution sb-small">
          {i.message}
        </p>
      ))}
    </div>
  );
}
