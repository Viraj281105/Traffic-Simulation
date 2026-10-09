import {
  ArrowUpRight,
  ChartSpline,
  History,
  Orbit,
  PencilRuler,
  Sigma,
  Split,
  TrafficCone,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { VIEW_ROUTES, followLink } from "../routing";
import { PLAIN_METRIC_MAP, metricDef } from "../metrics/plainLanguage";
import "./scenario/ScenarioBuilder.css";
import "./research/ResearchLab.css";
import { LabSection, ResearchLink } from "./research/LabSection";
import { WorkflowDiagram } from "./research/WorkflowDiagram";
import { ControlStrategies } from "./research/ControlStrategies";
import { MetricGallery } from "./research/MetricGallery";
import { ComparisonExplainer } from "./research/ComparisonExplainer";
import { EvidenceLadder } from "./research/EvidenceLadder";

interface Tool {
  href: string;
  title: string;
  body: string;
  use: string;
  icon: LucideIcon;
}

/** Where each activity lives, grouped by what you are doing. */
const TOOL_GROUPS: { id: string; title: string; tools: Tool[] }[] = [
  {
    id: "run",
    title: "Run a study",
    tools: [
      {
        href: VIEW_ROUTES.junction,
        icon: PencilRuler,
        title: "Your own junction",
        body: "Build or import a junction and compare the controls on it.",
        use: "How do the controls compare on my junction?",
      },
      {
        href: VIEW_ROUTES.threeWay,
        icon: Split,
        title: "Three-way study",
        body: "Fixed-time, adaptive and roundabout on matched seeds, with the exact method.",
        use: "How exactly is a comparison made?",
      },
      {
        href: VIEW_ROUTES.validation,
        icon: Sigma,
        title: "Statistical validation",
        body: "Monte Carlo study of signal against roundabout, with formal tests.",
        use: "Is a difference statistically robust?",
      },
      {
        href: VIEW_ROUTES.volume,
        icon: ChartSpline,
        title: "Traffic-level sweep",
        body: "Both controls across a range of demand levels.",
        use: "Where does the comparison change as traffic grows?",
      },
    ],
  },
  {
    id: "single",
    title: "Look closely at one control",
    tools: [
      {
        href: VIEW_ROUTES.signal,
        icon: TrafficCone,
        title: "Signal on its own",
        body: "A fixed-time or adaptive signal with its live metrics and phase state.",
        use: "How does the signal behave in detail?",
      },
      {
        href: VIEW_ROUTES.roundabout,
        icon: Orbit,
        title: "Roundabout on its own",
        body: "One roundabout with live metrics and circulating counts.",
        use: "How does the roundabout behave in detail?",
      },
    ],
  },
  {
    id: "audit",
    title: "Reproduce and audit",
    tools: [
      {
        href: VIEW_ROUTES.history,
        icon: History,
        title: "Saved runs & reproducibility",
        body: "Every saved run with its configuration, seed and code version.",
        use: "Can this result be reproduced?",
      },
    ],
  },
];

function ToolCard({ tool }: { tool: Tool }) {
  return (
    <a
      className="tool-card"
      href={tool.href}
      onClick={(e) => {
        followLink(e, tool.href);
      }}
    >
      <span className="tool-card-top" aria-hidden="true">
        <span className="tool-icon">
          <tool.icon size={18} strokeWidth={1.9} />
        </span>
        <ArrowUpRight size={16} className="tool-arrow" />
      </span>
      <span className="tool-use">{tool.use}</span>
      <span className="tool-title">{tool.title}</span>
      <span className="tool-body">{tool.body}</span>
    </a>
  );
}

/** The Research lab's front page: how UrbanFlow compares traffic controls,
 *  what its measures mean and how far its evidence reaches. The tools and
 *  the exact methods live on their own tabs; every section here points to
 *  the one that goes deeper. */
export function ResearchHub() {
  return (
    <div className="guided-page research-hub">
      <header className="guided-intro rl-hero">
        <p className="guided-eyebrow">Research lab</p>
        <h1>How UrbanFlow compares traffic control</h1>
        <p>
          UrbanFlow simulates traffic vehicle by vehicle and runs the same
          junction under different controls, so the differences you see come
          from the control alone. The result is reproducible evidence, not a
          verdict.
        </p>
        <nav className="rl-actions" aria-label="Start here">
          <a className="pb-btn pb-secondary" href="#workflow">
            How a study works
          </a>
          <a
            className="pb-btn pb-primary"
            href={VIEW_ROUTES.junction}
            onClick={(e) => {
              followLink(e, VIEW_ROUTES.junction);
            }}
          >
            Run a junction study
          </a>
          <a
            className="pb-btn pb-secondary"
            href={VIEW_ROUTES.validation}
            onClick={(e) => {
              followLink(e, VIEW_ROUTES.validation);
            }}
          >
            Statistical validation
          </a>
          <a
            className="pb-btn pb-secondary"
            href={VIEW_ROUTES.threeWay}
            onClick={(e) => {
              followLink(e, VIEW_ROUTES.threeWay);
            }}
          >
            Methodology
          </a>
        </nav>
      </header>

      <LabSection
        id="workflow"
        title="How a study proceeds"
        lede="Seven stages from a junction to a finding. What one stage produces is what the next one starts from."
        links={
          <ResearchLink to={VIEW_ROUTES.junction}>
            Set up a junction study
          </ResearchLink>
        }
      >
        <WorkflowDiagram />
      </LabSection>

      <LabSection
        id="strategies"
        title="Three ways to run a junction"
        lede="Each control is built on the same junction. They differ in how traffic is told to go."
        links={
          <>
            <ResearchLink to={VIEW_ROUTES.junction}>
              Compare them on your own junction
            </ResearchLink>
            <ResearchLink to={VIEW_ROUTES.signal}>
              Watch the signal on its own
            </ResearchLink>
          </>
        }
      >
        <ControlStrategies />
      </LabSection>

      <LabSection
        id="metrics"
        title="What the measures mean"
        lede="The measures a study reports, and what each can and cannot tell you."
        links={
          <ResearchLink to={VIEW_ROUTES.junction}>
            See them in a study result
          </ResearchLink>
        }
      >
        <MetricGallery />
        <details className="rl-more">
          <summary>All measures, by everyday question</summary>
          <div className="multi-run-scroll">
            <table className="plain-table">
              <thead>
                <tr>
                  <th scope="col">Everyday question</th>
                  <th scope="col">What it shows</th>
                  <th scope="col">Technical metrics</th>
                </tr>
              </thead>
              <tbody>
                {PLAIN_METRIC_MAP.map((row) => (
                  <tr key={row.question}>
                    <th scope="row">{row.question}</th>
                    <td>{row.plain}</td>
                    <td>
                      {row.keys.map((key) => (
                        <span key={key} className="metric-key">
                          {metricDef(key).label} <code>{key}</code>
                        </span>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </LabSection>

      <LabSection
        id="comparison"
        title="Why one run is not enough"
        lede="Traffic is random, so two runs of the same junction differ. A comparison has to show how much."
        links={
          <>
            <ResearchLink to={VIEW_ROUTES.validation}>
              Statistical uncertainty: validation
            </ResearchLink>
            <ResearchLink to={VIEW_ROUTES.threeWay}>
              The exact rule: three-way study
            </ResearchLink>
          </>
        }
      >
        <ComparisonExplainer />
      </LabSection>

      <LabSection
        id="evidence"
        title="What the evidence can and cannot say"
        lede="From a single run to a real-world claim, each step supports less than the next one needs."
        links={
          <ResearchLink to={VIEW_ROUTES.history}>
            Reproducibility: saved runs
          </ResearchLink>
        }
      >
        <EvidenceLadder />
      </LabSection>

      <LabSection
        id="tools"
        title="Where to go next"
        lede="Every tool has its own tab in the bar above."
      >
        {TOOL_GROUPS.map((group) => (
          <div key={group.id} className="rl-tool-group">
            <h3 className="rl-group-title">{group.title}</h3>
            <div className="tool-grid">
              {group.tools.map((tool) => (
                <ToolCard key={tool.href} tool={tool} />
              ))}
            </div>
          </div>
        ))}
      </LabSection>
    </div>
  );
}
