import { useState } from "react";
import { Map as MapIcon } from "lucide-react";
import "../insights/Insights.css";
import { Panel, StatGrid, StatTile } from "../components/dashboard/Dashboard";
import { errorText } from "../insights/http";
import { num } from "../insights/format";
import { previewRoadImport } from "./api";
import { ROAD_CLASSES, parseArea } from "./roadImport";
import { MessageList } from "./MessageList";
import type { ImportPreview, RoadClass } from "./types";

const WIDTH = 640;
const HEIGHT = 400;
const PAD = 16;

/** Roads of the preview drawn to scale (equirectangular, so shapes are right
 *  at city size). */
export function PreviewMap({ preview }: { preview: ImportPreview }) {
  const [w, s, e, n] = preview.bbox;
  const midLat = ((s + n) / 2) * (Math.PI / 180);
  const spanX = (e - w) * Math.cos(midLat);
  const spanY = n - s;
  const scale = Math.min(
    (WIDTH - 2 * PAD) / (spanX || 1),
    (HEIGHT - 2 * PAD) / (spanY || 1),
  );
  const px = (lon: number) => PAD + (lon - w) * Math.cos(midLat) * scale;
  const py = (lat: number) => HEIGHT - PAD - (lat - s) * scale;
  const width = (c: RoadClass) =>
    ({
      motorway: 4,
      trunk: 3.5,
      primary: 3,
      secondary: 2.4,
      tertiary: 1.8,
      residential: 1.2,
    })[c];
  return (
    <svg
      className="ins-preview"
      viewBox={`0 0 ${String(WIDTH)} ${String(HEIGHT)}`}
      role="img"
      aria-label={`Preview of ${String(preview.stats.linksShown)} roads in ${preview.area}`}
    >
      {preview.links.map((link) => (
        <polyline
          key={link.id}
          className="ins-preview__link"
          strokeWidth={width(link.roadClass)}
          points={link.geometry
            .map(([lon, lat]) => `${px(lon).toFixed(1)},${py(lat).toFixed(1)}`)
            .join(" ")}
        />
      ))}
    </svg>
  );
}

export function PreviewResult({ preview }: { preview: ImportPreview }) {
  const { stats } = preview;
  return (
    <div className="ins-stack" aria-live="polite">
      <StatGrid>
        <StatTile label="Roads" value={num(stats.links, 0)} />
        <StatTile label="Nodes" value={num(stats.nodes, 0)} />
        <StatTile
          label="Signalised junctions"
          value={num(stats.signalisedJunctions, 0)}
        />
        <StatTile
          label="Total length"
          value={num(stats.totalLengthKm, 1)}
          unit="km"
        />
      </StatGrid>
      <PreviewMap preview={preview} />
      {stats.linksShown < stats.links && (
        <p className="ins-muted">
          Showing {num(stats.linksShown, 0)} of {num(stats.links, 0)} roads to
          keep the preview fast.
        </p>
      )}
      <MessageList messages={preview.messages} />
    </div>
  );
}

/** Choose an area and road types, and see what an import would bring in. */
export function RoadImportPreview({
  preview: request = previewRoadImport,
}: {
  preview?: typeof previewRoadImport;
}) {
  const [area, setArea] = useState("");
  const [classes, setClasses] = useState<RoadClass[]>([
    "primary",
    "secondary",
    "tertiary",
  ]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ImportPreview | null>(null);

  const parsed = parseArea(area);
  const canRun = parsed !== null && classes.length > 0 && !busy;

  const run = () => {
    if (!parsed) return;
    setBusy(true);
    setError(null);
    request({ source: "osm", ...parsed, roadClasses: classes })
      .then(setResult)
      .catch((err: unknown) => {
        setResult(null);
        setError(errorText(err, "The preview could not be made."));
      })
      .finally(() => {
        setBusy(false);
      });
  };

  return (
    <Panel
      id="ins-import"
      title="Import roads from OpenStreetMap"
      subtitle="Preview what would be imported before anything is added."
    >
      <form
        className="ins-stack"
        onSubmit={(event) => {
          event.preventDefault();
          run();
        }}
      >
        <div className="uf-field">
          <label className="uf-label" htmlFor="ins-area">
            Place name or box
          </label>
          <input
            id="ins-area"
            className="uf-input"
            value={area}
            onChange={(e) => {
              setArea(e.target.value);
            }}
            aria-describedby="ins-area-hint"
          />
          <p id="ins-area-hint" className="uf-hint">
            A place such as &ldquo;Leeds city centre&rdquo;, or a box as west,
            south, east, north in degrees.
          </p>
          {area.trim() !== "" && parsed === null && (
            <p role="alert">
              That box is not valid: west must be less than east and south less
              than north.
            </p>
          )}
        </div>
        <fieldset className="uf-chip-row">
          <legend className="uf-label">Road types</legend>
          {ROAD_CLASSES.map((c) => (
            <label key={c.value} className="uf-chip-check">
              <input
                type="checkbox"
                checked={classes.includes(c.value)}
                onChange={(e) => {
                  setClasses((prev) =>
                    e.target.checked
                      ? [...prev, c.value]
                      : prev.filter((x) => x !== c.value),
                  );
                }}
              />
              {c.label}
            </label>
          ))}
        </fieldset>
        <div>
          <button
            type="submit"
            className="ins-btn ins-btn--primary"
            disabled={!canRun}
          >
            <MapIcon size={15} aria-hidden="true" />
            {busy ? "Loading…" : "Preview import"}
          </button>
        </div>
      </form>
      {error && <p role="alert">{error}</p>}
      {result && <PreviewResult preview={result} />}
    </Panel>
  );
}
