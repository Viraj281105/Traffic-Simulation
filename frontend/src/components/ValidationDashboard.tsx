import {
  BookOpen,
  ChartColumn,
  Download,
  Microscope,
  Settings2,
  Table,
  TriangleAlert,
} from "lucide-react";
import React, { useState } from "react";
import "./ValidationDashboard.css";
import { IntegrityCheck } from "./IntegrityCheck";
import { StudyProgress } from "./ui/StudyProgress";
import { useStudyJob } from "../hooks/useStudyJob";
import { STUDY_JOB_ROUTES } from "../services/studyJobs";
import { AdvancedConfigDrawer } from "./validation/AdvancedConfigDrawer";
import { MethodologyDrawer } from "./validation/MethodologyDrawer";
import { MethodologyTab } from "./validation/MethodologyTab";
import { SeedRunsTable } from "./validation/SeedRunsTable";
import { ValidationLaunchpad } from "./validation/ValidationLaunchpad";
import { VerdictBanner } from "./validation/VerdictBanner";
import { VisualComparisonTab } from "./validation/VisualComparisonTab";
import {
  DEFAULT_VALIDATION_SETTINGS,
  validationCsv,
  validationCustomConfig,
  type MetricKey,
  type ValidationResult,
  type ValidationSettings,
} from "./validation/validationModel";

/**
 * The Monte Carlo validation studio: repeats a signal-vs-roundabout
 * comparison over paired seeds and shows which differences are statistically
 * supported. This component owns the run settings, the background study job
 * and which view is open; each view lives in components/validation/.
 */
export const ValidationDashboard: React.FC = () => {
  const [settings, setSettings] = useState<ValidationSettings>(
    DEFAULT_VALIDATION_SETTINGS,
  );
  const updateSettings = (patch: Partial<ValidationSettings>) => {
    setSettings((prev) => ({ ...prev, ...patch }));
  };
  const { numSeeds, duration, confidenceLevel } = settings;
  const setNumSeeds = (value: number) => {
    updateSettings({ numSeeds: value });
  };
  const setDuration = (value: number) => {
    updateSettings({ duration: value });
  };

  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ValidationResult | null>(null);
  const [activeTab, setActiveTab] = useState<
    "visual" | "table" | "methodology"
  >("visual");
  const [chartMetric, setChartMetric] = useState<MetricKey>("delay");
  const [showMethodologyDrawer, setShowMethodologyDrawer] = useState(false);
  const [showConfigPanel, setShowConfigPanel] = useState(false);

  // Alpha of the next run (the result on screen carries its own).
  const alpha = Number((1 - confidenceLevel).toFixed(2));

  const study = useStudyJob();

  const launchValidation = (seeds: number, dur: number) => {
    setIsRunning(true);
    setError(null);
    setShowConfigPanel(false);

    study
      .run<ValidationResult>(STUDY_JOB_ROUTES.monteCarlo, {
        numSeeds: seeds,
        duration: dur,
        confidenceLevel,
        customConfig: validationCustomConfig(settings, dur),
      })
      .then((data) => {
        setResult(data);
        setIsRunning(false);
      })
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : "Validation failed");
        setIsRunning(false);
      });
  };

  const runValidation = () => {
    launchValidation(numSeeds, duration);
  };

  const handleLaunchPreset = (seeds: number, dur: number) => {
    updateSettings({ numSeeds: seeds, duration: dur });
    launchValidation(seeds, dur);
  };

  const exportValidationCSV = () => {
    if (!result) return;
    const csvContent = "data:text/csv;charset=utf-8," + validationCsv(result);
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute(
      "download",
      `monte_carlo_validation_n${result.numSeeds.toString()}_${duration.toString()}s.csv`,
    );
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const resultAlpha = result?.alpha ?? 0.05;
  const resultLevelPct = Math.round((result?.confidenceLevel ?? 0.95) * 100);

  return (
    <div className="validation-dashboard">
      {/* ── Top Executive Header Row ────────────────────────────── */}
      <div className="validation-header-row">
        <div className="uf-dash-head">
          <p className="guided-eyebrow">Research lab</p>
          <h1 className="uf-dash-head__title">
            <Microscope size={22} aria-hidden="true" className="uf-glyph" />
            Statistical Validation Studio
          </h1>
          <div className="uf-dash-head__tags">
            <span className="uf-tag">Monte Carlo engine</span>
            <span className="uf-tag is-positive">
              Next run: {Math.round(confidenceLevel * 100)}% confidence (α ={" "}
              {alpha})
            </span>
          </div>
          <p className="uf-dash-head__lead">
            Stochastic paired-seed simulation evaluating Fixed-Time Signal vs.
            Modern Roundabout under identical randomized traffic arrivals using
            Welch’s two-sample t-test and Cohen’s d effect sizes.
          </p>
          <p className="uf-dash-head__lead">
            This study uses its own configurable scenario (set under Advanced
            Config). To check a comparison you ran in Compare, use “How reliable
            is this?” on its results page — it repeats that exact scenario.
          </p>
        </div>

        <div className="validation-header-actions">
          {/* Inline Seeds & Duration selector in the same line as heading */}
          <div className="validation-header-inline-controls">
            <div className="validation-inline-param">
              <label htmlFor="validation-seeds">Seeds</label>
              <input
                id="validation-seeds"
                type="number"
                min={2}
                max={30}
                value={numSeeds}
                onChange={(e) => {
                  setNumSeeds(Number(e.target.value));
                }}
                title="Seeds (N): 2–30"
              />
            </div>
            <div className="validation-inline-param">
              <label htmlFor="validation-duration">Duration</label>
              <div className="validation-inline-unit-wrap">
                <input
                  id="validation-duration"
                  type="number"
                  min={10}
                  max={300}
                  step={10}
                  value={duration}
                  onChange={(e) => {
                    setDuration(Number(e.target.value));
                  }}
                  title="Duration per seed in seconds (10–300s)"
                />
                <span>s</span>
              </div>
            </div>
            <button
              type="button"
              className="validation-header-run-btn"
              onClick={runValidation}
              disabled={isRunning}
              title="Execute Monte Carlo validation"
            >
              {isRunning ? "Running…" : "Run"}
            </button>
          </div>

          {/* Config Settings Button named strictly 'Advanced Config' */}
          <button
            type="button"
            className={`validation-header-tool-btn ${showConfigPanel ? "active" : ""}`}
            onClick={() => {
              setShowConfigPanel((v) => !v);
            }}
            title="Configure advanced simulation and statistical parameters"
          >
            <Settings2 size={14} aria-hidden="true" className="uf-glyph" />{" "}
            Advanced Config
          </button>

          {/* Theory / Methodology Button */}
          <button
            type="button"
            className={`validation-header-tool-btn ${showMethodologyDrawer ? "active" : ""}`}
            onClick={() => {
              setShowMethodologyDrawer((v) => !v);
            }}
            title="Toggle statistical hypothesis & methodology reference"
          >
            <BookOpen size={14} aria-hidden="true" className="uf-glyph" />{" "}
            {showMethodologyDrawer ? "Hide Theory" : "Theory & Methodology"}
          </button>

          {result && (
            <button
              type="button"
              className="validation-export-csv-btn"
              onClick={exportValidationCSV}
              title="Download stochastic seed dataset as CSV"
            >
              <Download size={14} aria-hidden="true" className="uf-glyph" />{" "}
              Export CSV
            </button>
          )}
        </div>
      </div>

      {/* ── Collapsible Methodology Drawer ─────────────────────────── */}
      {showMethodologyDrawer && <MethodologyDrawer alpha={alpha} />}

      {/* ── Rich Advanced Configuration Drawer ─────────────────────── */}
      {showConfigPanel && (
        <AdvancedConfigDrawer
          settings={settings}
          onChange={updateSettings}
          onClose={() => {
            setShowConfigPanel(false);
          }}
          onReset={() => {
            setSettings(DEFAULT_VALIDATION_SETTINGS);
          }}
          onRun={runValidation}
          isRunning={isRunning}
        />
      )}

      {error && (
        <div className="validation-error">
          <TriangleAlert size={14} aria-hidden="true" className="uf-glyph" />{" "}
          {error}
        </div>
      )}

      {isRunning && (
        <StudyProgress
          title={`Monte Carlo validation · ${numSeeds.toString()} seeds × ${duration.toString()}s`}
          progress={study.progress}
        />
      )}

      {/* ── Empty State: Interactive Pre-Flight Launchpad ────────── */}
      {!result && !isRunning && (
        <ValidationLaunchpad onLaunchPreset={handleLaunchPreset} />
      )}

      {/* ── Validation Results View ──────────────────────────────── */}
      {result && !isRunning && (
        <>
          <VerdictBanner result={result} duration={duration} />
          {/* Studio Tab Bar */}
          <div className="validation-tab-bar">
            <button
              type="button"
              className={`val-tab-btn ${activeTab === "visual" ? "active" : ""}`}
              onClick={() => {
                setActiveTab("visual");
              }}
            >
              <ChartColumn size={14} aria-hidden="true" className="uf-glyph" />{" "}
              Visual Comparison & Charts
            </button>
            <button
              type="button"
              className={`val-tab-btn ${activeTab === "table" ? "active" : ""}`}
              onClick={() => {
                setActiveTab("table");
              }}
            >
              <Table size={14} aria-hidden="true" className="uf-glyph" />{" "}
              Per-Seed Raw Table ({result.numSeeds} trials)
            </button>
            <button
              type="button"
              className={`val-tab-btn ${activeTab === "methodology" ? "active" : ""}`}
              onClick={() => {
                setActiveTab("methodology");
              }}
            >
              <BookOpen size={14} aria-hidden="true" className="uf-glyph" />{" "}
              Statistical Method
            </button>
          </div>

          {activeTab === "visual" && (
            <VisualComparisonTab
              result={result}
              chartMetric={chartMetric}
              setChartMetric={setChartMetric}
            />
          )}
          {activeTab === "table" && (
            <SeedRunsTable result={result} onExportCsv={exportValidationCSV} />
          )}
          {activeTab === "methodology" && (
            <MethodologyTab
              resultAlpha={resultAlpha}
              resultLevelPct={resultLevelPct}
            />
          )}
        </>
      )}

      <IntegrityCheck />
    </div>
  );
};
