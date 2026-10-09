import type { ReactNode } from "react";
import { metricDef } from "../../metrics/plainLanguage";
import type { MetricDef } from "../../metrics/catalog";
import {
  CloseApproachArt,
  DelayArt,
  NotModelledArt,
  QueueArt,
  QueuedArt,
  ReliabilityArt,
  ServedArt,
  SpeedArt,
  StopsArt,
} from "./MetricArt";

interface Explainer {
  id: string;
  /** Catalog keys this card explains; names and exact definitions come from
   *  the metric catalog so the wording never drifts from it. */
  keys: MetricDef["key"][];
  /** Shown when the card covers something the catalog does not measure. */
  title?: string;
  art: ReactNode;
  means: string;
  why: string;
  example: string;
  caveat: string;
  unavailable?: boolean;
}

interface Group {
  id: string;
  title: string;
  cards: Explainer[];
}

const GROUPS: Group[] = [
  {
    id: "time",
    title: "Time lost",
    cards: [
      {
        id: "delay",
        keys: ["averageDelay"],
        art: <DelayArt />,
        means:
          "The extra time a vehicle takes compared with the same journey at its own desired speed.",
        why: "It is the time drivers actually lose, including slowing the layout itself forces.",
        example:
          "An average delay of 30 s means a typical vehicle took 30 s longer than an empty junction would have allowed.",
        caveat:
          "An average hides spread: the 95th percentile delay shows what the slowest 1 in 20 drivers lose.",
      },
      {
        id: "queued",
        keys: ["averageWaitTime"],
        art: <QueuedArt />,
        means: "The time each vehicle spends nearly stopped, below 0.5 m/s.",
        why: "It separates standing in a queue from merely slowing down.",
        example:
          "A vehicle that rolls slowly for 20 s is delayed but not queued.",
        caveat:
          "Not the same as delay. A control that keeps traffic rolling can show little queued time and still add delay.",
      },
      {
        id: "stops",
        keys: ["averageStopsPerVehicle"],
        art: <StopsArt />,
        means: "How many times a typical vehicle comes to a stop.",
        why: "Stop-and-go driving is part of what drivers experience at a junction.",
        example: "1.5 means vehicles typically stopped more than once.",
        caveat:
          "It counts stops, not how long they last. Read it with queued time.",
      },
    ],
  },
  {
    id: "flow",
    title: "Traffic moved",
    cards: [
      {
        id: "served",
        keys: ["throughput"],
        art: <ServedArt />,
        means: "Vehicles that made it through the junction after the warm-up.",
        why: "It shows how much traffic the junction actually moved.",
        example:
          "Compare it with vehicles generated: a large gap means vehicles were still waiting or travelling when the run ended.",
        caveat:
          "Higher is not automatically better. Below the junction's capacity it mostly reflects demand, not the control, and it says nothing about delay.",
      },
      {
        id: "queue",
        keys: ["averageQueueLength"],
        art: <QueueArt />,
        means: "The typical number of vehicles waiting on one approach.",
        why: "It shows how much waiting traffic a design has to hold.",
        example:
          "An average of 4 means about four vehicles were queued on a typical approach at a time.",
        caveat:
          "A smaller queue is not always better: fewer arrivals or bursty releases can shrink it. Read it with delay and vehicles served.",
      },
      {
        id: "speed",
        keys: ["averageTravelSpeed"],
        art: <SpeedArt />,
        means: "The mean speed of the vehicles in the network right now.",
        why: "A live sign of free-flowing traffic versus crawling.",
        example:
          "A drop to a few m/s while the queue grows means traffic is crawling.",
        caveat:
          "A snapshot of one moment, not a run average, so it rises and falls during a run.",
      },
    ],
  },
  {
    id: "trust",
    title: "Reliability and risk",
    cards: [
      {
        id: "reliability",
        keys: ["travelTimeReliability"],
        art: <ReliabilityArt />,
        means:
          "The 95th percentile journey time divided by the median journey time.",
        why: "It shows how much longer to allow for a bad trip than for a typical one.",
        example:
          "1.0 is perfectly reliable; 1.5 means a bad trip takes about 50 % longer than a typical one.",
        caveat:
          "Flagged when fewer than 20 vehicles back it. UrbanFlow reports this index rather than a plain average travel time.",
      },
      {
        id: "close",
        keys: ["minTTC", "minPET"],
        art: <CloseApproachArt />,
        means:
          "How close two vehicles on crossing paths came, as the time before they would reach the same point.",
        why: "Crashes are too rare to count, so shorter times are used as a stand-in for conflict.",
        example:
          "A minimum time-to-collision of 1.5 s means two vehicles on different lanes came within 1.5 s of colliding had neither changed.",
        caveat:
          "A surrogate indicator, not a crash probability. The post-encroachment time is measured at signals only. Collisions are an integrity check on the model, not a risk estimate.",
      },
      {
        id: "emissions",
        keys: [],
        title: "Fuel use and emissions",
        art: <NotModelledArt />,
        means: "Not measured: UrbanFlow has no fuel or emissions model.",
        why: "Stops per vehicle and queued time describe stop-and-go driving only.",
        example: "No fuel or CO₂ figure appears anywhere in a result.",
        caveat: "Do not read either indicator as an emissions estimate.",
        unavailable: true,
      },
    ],
  },
];

function Card({ card }: { card: Explainer }) {
  const defs = card.keys.map((k) => metricDef(k));
  const name = card.title ?? defs.map((d) => d.label).join(" · ");
  const unit = defs.length === 1 && defs[0].unit ? defs[0].unit : null;
  return (
    <article
      className={`rl-metric${card.unavailable ? " is-unavailable" : ""}`}
      aria-labelledby={`metric-${card.id}`}
    >
      {card.art}
      <h4 id={`metric-${card.id}`}>
        {name}
        {unit && <span className="rl-unit">{unit}</span>}
        {card.unavailable && <span className="rl-unit">not available</span>}
      </h4>
      <p>{card.means}</p>
      <details>
        <summary>How to read it</summary>
        <dl>
          <dt>Why it matters</dt>
          <dd>{card.why}</dd>
          <dt>Reading an example</dt>
          <dd>{card.example}</dd>
          <dt>Keep in mind</dt>
          <dd>{card.caveat}</dd>
          {defs.length > 0 && <dt>Exact definition</dt>}
          {defs.map((d) => (
            <dd key={d.key} className="rl-exact">
              <code>{d.key}</code> {d.description}
            </dd>
          ))}
        </dl>
      </details>
    </article>
  );
}

/** The measures a study reports, drawn so the idea is clear before the
 *  definition is read. Names and exact definitions come from the catalog;
 *  what UrbanFlow does not measure is shown as such. */
export function MetricGallery() {
  return (
    <div className="rl-metric-groups">
      {GROUPS.map((group) => (
        <div key={group.id} className="rl-metric-group">
          <h3 className="rl-group-title">{group.title}</h3>
          <div className="rl-metric-grid">
            {group.cards.map((card) => (
              <Card key={card.id} card={card} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
