import { useState } from "react";
import { Ambulance, Bus } from "lucide-react";
import "../netcommon/network.css";
import { EmptyHint, Panel, Skeleton } from "../components/dashboard/Dashboard";
import { NumberField } from "../netcommon/NumberField";
import { useAction } from "../netcommon/useAction";
import { SelectField } from "../rescommon/SelectField";
import { useLoad } from "../rescommon/useLoad";
import { compareEmergency, compareTransit, getPriorityCatalogue } from "./api";
import { EmergencyResult } from "./EmergencyResult";
import { TransitResult } from "./TransitResult";
import type {
  Approach,
  EmergencyComparison,
  Method,
  PriorityCatalogue,
  TransitComparison,
  Turn,
} from "./types";

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const opts = <T extends string>(list: readonly T[]) =>
  list.map((id) => ({ id, label: cap(id.replace("_", " ")) }));

function CommonFields({
  catalogue,
  duration,
  setDuration,
  rate,
  setRate,
  seeds,
  setSeeds,
  method,
  setMethod,
}: {
  catalogue: PriorityCatalogue;
  duration: number;
  setDuration: (v: number) => void;
  rate: number;
  setRate: (v: number) => void;
  seeds: number;
  setSeeds: (v: number) => void;
  method: Method;
  setMethod: (v: Method) => void;
}) {
  const [dLo, dHi] = catalogue.limits.durationSeconds;
  const [sLo, sHi] = catalogue.limits.seeds;
  return (
    <>
      <NumberField
        label="Run length (s)"
        value={duration}
        min={dLo}
        max={dHi}
        onChange={setDuration}
      />
      <NumberField
        label="Vehicles per second, whole junction"
        value={rate}
        min={0.05}
        max={2}
        step={0.05}
        onChange={setRate}
      />
      <NumberField
        label="Seeds"
        value={seeds}
        min={sLo}
        max={sHi}
        onChange={(v) => {
          setSeeds(Math.round(v));
        }}
      />
      <SelectField
        label="Statistical method"
        value={method}
        options={[
          { id: "paired_t", label: "Paired t interval" },
          { id: "paired_bootstrap", label: "Paired bootstrap" },
        ]}
        onChange={setMethod}
      />
    </>
  );
}

function Emergency({ catalogue }: { catalogue: PriorityCatalogue }) {
  const [duration, setDuration] = useState(200);
  const [rate, setRate] = useState(1.2);
  const [seeds, setSeeds] = useState(4);
  const [method, setMethod] = useState<Method>("paired_t");
  const [kind, setKind] = useState(
    catalogue.emergencyKinds[0]?.id ?? "ambulance",
  );
  const [approach, setApproach] = useState<Approach>("north");
  const [turn, setTurn] = useState<Turn>("straight");
  const [at, setAt] = useState(100);
  const [state, start] = useAction<EmergencyComparison>(
    "The emergency comparison could not be run.",
  );
  return (
    <Panel
      id="res-emergency"
      title="Emergency vehicle pre-emption"
      subtitle="The same traffic and the same ambulance, with the signals pre-empting and without."
    >
      <div className="nw-stack">
        <form
          className="nw-form"
          onSubmit={(e) => {
            e.preventDefault();
            start(() =>
              compareEmergency({
                durationSeconds: duration,
                arrivalRate: rate,
                numSeeds: seeds,
                method,
                kind,
                approach,
                turn,
                timeSeconds: at,
              }),
            );
          }}
        >
          <SelectField
            label="Emergency vehicle"
            value={kind}
            options={catalogue.emergencyKinds.map((k) => ({
              id: k.id,
              label: k.label,
            }))}
            onChange={setKind}
          />
          <SelectField
            label="Arrives from"
            value={approach}
            options={opts(catalogue.approaches)}
            onChange={setApproach}
          />
          <SelectField
            label="Turn"
            value={turn}
            options={opts(catalogue.turns)}
            onChange={setTurn}
          />
          <NumberField
            label="Enters at (s)"
            value={at}
            min={0}
            max={catalogue.limits.durationSeconds[1]}
            onChange={setAt}
          />
          <CommonFields
            catalogue={catalogue}
            duration={duration}
            setDuration={setDuration}
            rate={rate}
            setRate={setRate}
            seeds={seeds}
            setSeeds={setSeeds}
            method={method}
            setMethod={setMethod}
          />
          <button
            type="submit"
            className="nw-btn nw-btn--primary"
            disabled={state.status === "loading"}
          >
            Compare emergency response
          </button>
        </form>
        {state.status === "idle" && (
          <EmptyHint icon={<Ambulance size={22} />} title="No comparison yet">
            Press Compare emergency response to run every seed twice.
          </EmptyHint>
        )}
        {state.status === "loading" && <Skeleton lines={5} />}
        {state.status === "error" && <p role="alert">{state.message}</p>}
        {state.status === "ready" && <EmergencyResult result={state.data} />}
      </div>
    </Panel>
  );
}

function Transit({ catalogue }: { catalogue: PriorityCatalogue }) {
  const [duration, setDuration] = useState(300);
  const [rate, setRate] = useState(1.2);
  const [seeds, setSeeds] = useState(4);
  const [method, setMethod] = useState<Method>("paired_t");
  const [approach, setApproach] = useState<Approach>("north");
  const [turn, setTurn] = useState<Turn>("straight");
  const [headway, setHeadway] = useState(90);
  const [trips, setTrips] = useState(3);
  const [state, start] = useAction<TransitComparison>(
    "The transit comparison could not be run.",
  );
  return (
    <Panel
      id="res-transit"
      title="Transit priority"
      subtitle="Buses given extra green only when they are running late, against no priority."
    >
      <div className="nw-stack">
        <form
          className="nw-form"
          onSubmit={(e) => {
            e.preventDefault();
            start(() =>
              compareTransit({
                durationSeconds: duration,
                arrivalRate: rate,
                numSeeds: seeds,
                method,
                approach,
                turn,
                headwaySeconds: headway,
                trips,
              }),
            );
          }}
        >
          <SelectField
            label="Bus approach"
            value={approach}
            options={opts(catalogue.approaches)}
            onChange={setApproach}
          />
          <SelectField
            label="Bus turn"
            value={turn}
            options={opts(catalogue.turns)}
            onChange={setTurn}
          />
          <NumberField
            label="Gap between buses (s)"
            value={headway}
            min={30}
            max={900}
            onChange={setHeadway}
          />
          <NumberField
            label="Buses"
            value={trips}
            min={1}
            max={catalogue.limits.tripsPerLine}
            onChange={(v) => {
              setTrips(Math.round(v));
            }}
          />
          <CommonFields
            catalogue={catalogue}
            duration={duration}
            setDuration={setDuration}
            rate={rate}
            setRate={setRate}
            seeds={seeds}
            setSeeds={setSeeds}
            method={method}
            setMethod={setMethod}
          />
          <button
            type="submit"
            className="nw-btn nw-btn--primary"
            disabled={state.status === "loading"}
          >
            Compare transit priority
          </button>
        </form>
        {state.status === "idle" && (
          <EmptyHint icon={<Bus size={22} />} title="No comparison yet">
            Press Compare transit priority to run every seed twice.
          </EmptyHint>
        )}
        {state.status === "loading" && <Skeleton lines={5} />}
        {state.status === "error" && <p role="alert">{state.message}</p>}
        {state.status === "ready" && <TransitResult result={state.data} />}
      </div>
    </Panel>
  );
}

/** Priority tab: emergency pre-emption and transit priority, each compared
 *  with and without over paired seeds. */
export function PriorityTab() {
  const catalogue = useLoad(
    getPriorityCatalogue,
    "The priority options could not be loaded.",
  );
  if (catalogue.status === "loading") return <Skeleton lines={4} />;
  if (catalogue.status === "error") {
    return <p role="alert">{catalogue.message}</p>;
  }
  return (
    <div className="nw-stack">
      <Emergency catalogue={catalogue.data} />
      <Transit catalogue={catalogue.data} />
      <section className="nw-stack" aria-label="Assumptions">
        <h3 className="nw-headline">Assumptions</h3>
        <ul className="nw-facts">
          {catalogue.data.assumptions.map((a) => (
            <li key={a}>{a}</li>
          ))}
        </ul>
        <p className="nw-muted">{catalogue.data.label}</p>
      </section>
    </div>
  );
}
