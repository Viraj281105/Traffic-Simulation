import {
  Info,
  Microscope,
  Scale,
  ShieldAlert,
  Sprout,
  Trophy,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface Rung {
  title: string;
  shows: string;
  doesNot: string;
}

/** What each kind of result can and cannot support, from one run upwards. */
const RUNGS: Rung[] = [
  {
    title: "A measured simulation output",
    shows: "What happened in one run, with one random arrival pattern.",
    doesNot: "That the next run, or the other control, would behave the same.",
  },
  {
    title: "A pattern across repeated runs",
    shows: "The average over several seeds, with its 95 % interval.",
    doesNot: "That two controls differ: overlapping intervals say little.",
  },
  {
    title: "A statistically supported difference",
    shows:
      "The interval of the paired gaps excludes 0 and the gap is larger than the tie tolerance.",
    doesNot: "That the gap matters in practice, or holds for another junction.",
  },
];

const KEEP_IN_MIND: { icon: LucideIcon; text: string }[] = [
  {
    icon: Sprout,
    text: "Results depend on the assumptions and the configuration they were run with.",
  },
  {
    icon: Scale,
    text: "Calibration is against UrbanFlow’s own measured capacity, not observed traffic, so it does not prove real-world accuracy.",
  },
  {
    icon: ShieldAlert,
    text: "Safety indicators are surrogate proxies, not measured crash risk.",
  },
  {
    icon: Info,
    text: "There is no emissions model: no fuel or CO₂ figure is produced.",
  },
  {
    icon: Microscope,
    text: "A statistically supported gap is not automatically a practically important one.",
  },
  {
    icon: Trophy,
    text: "UrbanFlow does not declare one design better everywhere; a result holds for the setup that produced it.",
  },
];

export function EvidenceLadder() {
  return (
    <div className="rl-evidence">
      <ol
        className="rl-ladder"
        aria-label="Evidence ladder, from one run to a real-world claim"
      >
        {RUNGS.map((rung, i) => (
          <li
            key={rung.title}
            className="rl-rung"
            style={{ "--rung": i } as React.CSSProperties}
          >
            <span className="rl-rung-n" aria-hidden="true">
              {i + 1}
            </span>
            <div>
              <h3>{rung.title}</h3>
              <p>
                <span className="rl-tag is-yes">Shows</span> {rung.shows}
              </p>
              <p>
                <span className="rl-tag is-no">Does not show</span>{" "}
                {rung.doesNot}
              </p>
            </div>
            {i === 1 && (
              <p className="rl-branch">
                <strong>Inconclusive</strong> is a result of its own: the runs
                cannot separate the controls. It is not “no difference”.
              </p>
            )}
          </li>
        ))}
        <li
          className="rl-rung is-outside"
          style={{ "--rung": 3 } as React.CSSProperties}
        >
          <span className="rl-rung-n" aria-hidden="true">
            4
          </span>
          <div>
            <h3>A real-world claim</h3>
            <p>
              <span className="rl-tag is-no">Outside the simulation</span> Needs
              evidence UrbanFlow does not produce, such as observations from the
              junction itself.
            </p>
          </div>
        </li>
      </ol>

      <div>
        <h3 className="rl-group-title">Keep in mind</h3>
        <ul className="rl-keep">
          {KEEP_IN_MIND.map(({ icon: Icon, text }) => (
            <li key={text}>
              <Icon size={16} aria-hidden="true" />
              <span>{text}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
