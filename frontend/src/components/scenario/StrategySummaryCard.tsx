/**
 * Strategy Summary UI / "Strategy DNA Card" (V3.0 W3, ADR-014, W3-T4).
 *
 * Displays the resolved strategy configuration and its 6 structural layers:
 * 1. Geometry Constraint
 * 2. Movement Topology
 * 3. Right-of-Way Rule
 * 4. Control Policy
 * 5. Adaptation Logic
 * 6. Priority Overlay
 *
 * Clearly distinguishes selected strategies from resolved defaults, tracks parameter
 * provenance, and surfaces compatibility validation diagnostics (compat.*).
 */

import { useId, useMemo, useState } from "react";
import type { ScenarioDocument, Strategy } from "../../scenario/scenarioTypes";
import {
  BUILTIN_STRATEGY_DESCRIPTORS,
  evaluateStrategyCompatibility,
  resolveActiveStrategyId,
  resolveParameterProvenance,
  resolveStrategyLayers,
  toCanonicalStrategyId,
  type CanonicalStrategyId,
} from "../../scenario/strategySummaryModel";
import "./StrategySummaryCard.css";

export interface StrategySummaryCardProps {
  scenario: ScenarioDocument;
  /** Strategies enabled for comparison/run (e.g. ['fixed_time', 'roundabout']). */
  strategies?: Strategy[];
  /** Optional active tab override. */
  activeStrategy?: Strategy | CanonicalStrategyId;
  onSelectStrategy?: (s: CanonicalStrategyId) => void;
  /** Server-reported validation errors for compatibility code extraction. */
  serverErrors?: string[];
  /** Compact presentation mode. */
  compact?: boolean;
}

export function StrategySummaryCard({
  scenario,
  strategies,
  activeStrategy: controlledStrategy,
  onSelectStrategy,
  serverErrors = [],
  compact = false,
}: StrategySummaryCardProps) {
  const ids = useId();
  const primaryId = useMemo(
    () => resolveActiveStrategyId(scenario),
    [scenario],
  );

  // If strategies are supplied, allow user to inspect any of the candidate strategies
  const [internalSelectedId, setInternalSelectedId] =
    useState<CanonicalStrategyId | null>(null);

  const activeId: CanonicalStrategyId = useMemo(() => {
    if (controlledStrategy) {
      return toCanonicalStrategyId(controlledStrategy, scenario);
    }
    if (internalSelectedId) {
      return internalSelectedId;
    }
    return primaryId;
  }, [controlledStrategy, internalSelectedId, primaryId, scenario]);

  const descriptor = BUILTIN_STRATEGY_DESCRIPTORS[activeId];

  // Evaluate compatibility
  const issues = useMemo(
    () => evaluateStrategyCompatibility(activeId, scenario, serverErrors),
    [activeId, scenario, serverErrors],
  );

  // Evaluate layers
  const layers = useMemo(
    () => resolveStrategyLayers(activeId, scenario, issues),
    [activeId, scenario, issues],
  );

  // Evaluate parameters provenance
  const provenance = useMemo(
    () => resolveParameterProvenance(activeId, scenario),
    [activeId, scenario],
  );

  const isPrimary = activeId === primaryId;

  // Determine selection status tag:
  // Is this strategy explicitly selected in the junction configuration or is it default?
  const selectionStatus = useMemo(() => {
    if (isPrimary) {
      if (scenario.preset) {
        return {
          label: "Preset Selected",
          type: "selected" as const,
          description: `Active configuration matching scenario junction choice (${descriptor.name}).`,
        };
      }
      return {
        label: "User Selected",
        type: "selected" as const,
        description: `Active configuration matching scenario junction choice (${descriptor.name}).`,
      };
    }
    return {
      label: "Comparison Alternative",
      type: "default" as const,
      description: `Evaluated candidate strategy in multi-control comparison suite.`,
    };
  }, [isPrimary, scenario.preset, descriptor.name]);

  const candidateIds = useMemo(() => {
    if (!strategies || strategies.length <= 1) return [];
    const set = new Set<CanonicalStrategyId>();
    for (const s of strategies) {
      set.add(toCanonicalStrategyId(s, scenario));
    }
    // Always include the scenario's primary strategy
    set.add(primaryId);
    return Array.from(set);
  }, [strategies, scenario, primaryId]);

  return (
    <div
      className={`strategy-dna-card${issues.length > 0 ? " has-conflict" : ""}`}
      role="region"
      aria-label="Strategy DNA and layer contract"
      id={`${ids}-dna-card`}
    >
      {/* Header */}
      <div className="strategy-dna-head">
        <div className="strategy-dna-title-row">
          <h4 className="strategy-dna-title">
            <span className="strategy-dna-icon" aria-hidden="true">
              🧬
            </span>
            Strategy DNA &amp; Contract
          </h4>
          <div className="strategy-badges-row">
            <span
              className={`strategy-badge-pill is-${selectionStatus.type}`}
              title={selectionStatus.description}
            >
              {selectionStatus.label}
            </span>
            <span className="strategy-badge-pill is-status">
              {descriptor.status}
            </span>
            <span
              className="strategy-fingerprint"
              title="Deterministic 16-hex strategy fingerprint"
            >
              {descriptor.fingerprint}
            </span>
          </div>
        </div>

        {/* Candidate Tabs (if multi-strategy context) */}
        {candidateIds.length > 1 && (
          <nav
            className="strategy-tabs-nav"
            aria-label="Inspect candidate strategies"
          >
            {candidateIds.map((cid) => {
              const cDesc = BUILTIN_STRATEGY_DESCRIPTORS[cid];
              const isActive = cid === activeId;
              const isCurPrimary = cid === primaryId;
              return (
                <button
                  key={cid}
                  type="button"
                  className={`strategy-tab-btn${isActive ? " is-active" : ""}`}
                  aria-pressed={isActive}
                  onClick={() => {
                    setInternalSelectedId(cid);
                    onSelectStrategy?.(cid);
                  }}
                >
                  {cDesc.name}
                  {isCurPrimary ? " (Primary)" : ""}
                </button>
              );
            })}
          </nav>
        )}

        {/* Strategy Description Banner */}
        <div className="strategy-name-banner">
          <span className="strategy-name-text">{descriptor.name}</span>
          <p className="strategy-desc-text">{descriptor.description}</p>
        </div>
      </div>

      {/* Compatibility Conflict Alerts (if any) */}
      {issues.length > 0 && (
        <div className="strategy-compat-alert" role="alert">
          <p className="strategy-compat-title">
            <span aria-hidden="true">⚠️</span> Compatibility Warning
          </p>
          {issues.map((iss) => (
            <div key={iss.code} className="strategy-compat-item">
              <p className="strategy-compat-message">
                <strong className="strategy-compat-code">[{iss.code}]</strong>{" "}
                {iss.message}
              </p>
              {iss.suggestion && (
                <p className="strategy-compat-suggestion">
                  Suggestion: {iss.suggestion}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* 6-Layer DNA Breakdown */}
      <div className="strategy-layers-section">
        <div className="strategy-layers-head">
          <span>6-Layer Architecture Contract</span>
          <span className="sb-muted">Layers 1–6</span>
        </div>
        <ol className="strategy-layers-list">
          {layers.map((l) => (
            <li
              key={l.layerKey}
              className={`strategy-layer-row${l.hasConflict ? " has-conflict" : ""}`}
            >
              <span className="strategy-layer-num" aria-hidden="true">
                {l.layerIndex}
              </span>
              <div className="strategy-layer-content">
                <div className="strategy-layer-title-row">
                  <span className="strategy-layer-title">{l.layerTitle}</span>
                  <span className="strategy-layer-contract">
                    {l.contractValue}
                  </span>
                </div>
                <span className="strategy-layer-applied">
                  Applied: {l.appliedValue}
                </span>
                {l.conflictMessage && (
                  <span className="strategy-layer-conflict">
                    ⚠️ {l.conflictMessage}
                  </span>
                )}
              </div>
            </li>
          ))}
        </ol>
      </div>

      {/* Parameters Provenance (Defaults vs Customized) */}
      {!compact && (
        <div className="strategy-provenance-box">
          <div className="strategy-provenance-head">
            <span
              className={`strategy-provenance-status${!provenance.isAllDefault ? " is-custom" : ""}`}
            >
              {provenance.isAllDefault
                ? `Configuration: All ${String(provenance.totalParameters)} parameters at factory defaults`
                : `Configuration: ${String(provenance.customizedCount)} of ${String(provenance.totalParameters)} parameters customized`}
            </span>
          </div>
          <details className="strategy-params-details">
            <summary>View strategy parameters &amp; values</summary>
            <div className="strategy-params-grid">
              {provenance.parameters.map((p) => (
                <div key={p.name} className="strategy-param-item">
                  <span className="strategy-param-name">{p.label}</span>
                  <span
                    className={`strategy-param-val${!p.isDefault ? " is-custom" : ""}`}
                  >
                    {typeof p.currentValue === "number"
                      ? `${String(p.currentValue)} ${p.unit}`
                      : p.currentValue}
                    {!p.isDefault ? " (custom)" : " (default)"}
                  </span>
                </div>
              ))}
            </div>
          </details>
        </div>
      )}

      {/* Limitations / Not Modelled */}
      {!compact && descriptor.notModelled.length > 0 && (
        <details className="strategy-limitations">
          <summary>
            Model Boundaries ({descriptor.notModelled.length} not modelled)
          </summary>
          <ul className="strategy-limitations-list">
            {descriptor.notModelled.map((nm) => (
              <li key={nm}>{nm}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
