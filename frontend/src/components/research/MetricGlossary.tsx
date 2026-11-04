import { useMemo, useState } from "react";
import {
  filterGlossary,
  glossaryEntries,
  GLOSSARY_GROUPS,
} from "../../metrics/glossary";

/** Every measure, in everyday words, searchable. Reads the metric catalog
 *  (metrics/glossary.ts), so it always matches the tables and the docs page. */
export function MetricGlossary() {
  const [query, setQuery] = useState("");
  const all = useMemo(() => glossaryEntries(), []);
  const shown = useMemo(() => filterGlossary(all, query), [all, query]);

  return (
    <section className="metric-glossary" aria-label="Metric glossary">
      <label className="metric-glossary-search">
        <span>Search the measures</span>
        <input
          type="search"
          value={query}
          placeholder="For example: queue, safety, fuel"
          onChange={(e) => {
            setQuery(e.target.value);
          }}
        />
      </label>
      <p role="status" className="metric-glossary-count">
        {shown.length === 0
          ? "No measure matches that search."
          : `${String(shown.length)} of ${String(all.length)} measures`}
      </p>
      {GLOSSARY_GROUPS.map((group) => {
        const entries = shown.filter((e) => e.group === group.id);
        if (entries.length === 0) return null;
        return (
          <section key={group.id} aria-labelledby={`glossary-${group.id}`}>
            <h4 id={`glossary-${group.id}`}>{group.title}</h4>
            <dl>
              {entries.map((e) => (
                <div key={e.key} className="metric-glossary-entry">
                  <dt>
                    {e.label}
                    {e.unit ? <span> ({e.unit})</span> : null}{" "}
                    <code>{e.key}</code>
                  </dt>
                  <dd>
                    <p>{e.text}</p>
                    {e.caveats.length > 0 && (
                      <ul>
                        {e.caveats.map((c) => (
                          <li key={c}>{c}</li>
                        ))}
                      </ul>
                    )}
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        );
      })}
    </section>
  );
}
