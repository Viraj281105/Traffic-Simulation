import { useEffect, useState } from "react";
import {
  CalendarClock,
  Check,
  Clipboard,
  Eye,
  EyeOff,
  KeyRound,
  Layers,
  ShieldAlert,
  Trash2,
} from "lucide-react";
import "../copilot/Copilot.css";
import "../discovery/Discovery.css";
import {
  SCOPES,
  createToken,
  listTokens,
  revokeToken,
  type CreatedToken,
  type Scope,
  type TokenMetadata,
} from "../../services/v3/tokens";
import { CHANGES_DATA, daysLeft, lifeLeft, scopeCoverage } from "./tokenStats";
import { ExperimentsApiError } from "../../services/v3/experiments";
import {
  EmptyHint,
  Meter,
  PageHero,
  Panel,
  Pill,
  Skeleton,
  StatGrid,
  StatTile,
  type Tone,
} from "../dashboard/Dashboard";

const SCOPE_TEXT: Record<Scope, string> = {
  "experiments:read": "Read experiments and capabilities",
  "experiments:run": "Submit, cancel, resume and delete experiments",
  "packages:read": "Download packages",
  "packages:write": "Verify uploaded packages",
  "tokens:read": "List your tokens",
  "tokens:manage": "Revoke your tokens",
};

const PRESETS: { label: string; scopes: Scope[]; hint: string }[] = [
  {
    label: "Read-only",
    scopes: ["experiments:read", "packages:read"],
    hint: "Look at experiments and download packages",
  },
  {
    label: "Run experiments",
    scopes: ["experiments:read", "experiments:run", "packages:read"],
    hint: "What the Python client needs to submit and fetch",
  },
];

const MAX_TOKENS = 10;
const SOON_DAYS = 7;

function message(err: unknown, fallback: string): string {
  return err instanceof ExperimentsApiError ? err.message : fallback;
}

function expiryTone(days: number): Tone {
  return days <= 3 ? "bad" : days <= SOON_DAYS ? "warn" : "good";
}

/** Personal access tokens for the Python client and scripts. Created only
 *  here (a signed-in browser session); the secret is shown once. */
export function TokensPage() {
  const [tokens, setTokens] = useState<TokenMetadata[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [name, setName] = useState("My script");
  const [scopes, setScopes] = useState<Scope[]>(["experiments:read"]);
  const [days, setDays] = useState(30);
  const [created, setCreated] = useState<CreatedToken | null>(null);
  const [revealed, setRevealed] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const [now] = useState(() => Date.now());

  useEffect(() => {
    listTokens()
      .then((r) => {
        setTokens(r.tokens);
      })
      .catch((err: unknown) => {
        setError(message(err, "Your tokens could not be loaded."));
      })
      .finally(() => {
        setLoaded(true);
      });
  }, [tick]);

  const toggle = (scope: Scope) => {
    setScopes((prev) =>
      prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope],
    );
  };

  const create = () => {
    setError(null);
    createToken({ name, scopes, expiresInDays: days })
      .then((t) => {
        setCreated(t);
        setRevealed(false);
        setCopied(false);
        setTick((n) => n + 1);
      })
      .catch((err: unknown) => {
        setError(message(err, "The token could not be created."));
      });
  };

  const copy = () => {
    if (!created) return;
    void navigator.clipboard
      .writeText(created.token)
      .then(() => {
        setCopied(true);
      })
      .catch(() => {
        setCopied(false);
      });
  };

  const coverage = scopeCoverage(tokens);
  const expiringSoon = tokens.filter(
    (t) => daysLeft(t.expiresAt, now) <= SOON_DAYS,
  ).length;
  const neverUsed = tokens.filter((t) => !t.lastUsedAt).length;
  const canChange = tokens.filter((t) =>
    t.scopes.some((s) => CHANGES_DATA[s]),
  ).length;
  const maxCover = Math.max(1, ...Object.values(coverage));
  const atLimit = tokens.length >= MAX_TOKENS;
  const newChangesData = scopes.some((s) => CHANGES_DATA[s]);

  return (
    <div className="dash-page copilot-page">
      <PageHero eyebrow="Developer" title="API tokens">
        Personal access tokens let the Python client and your scripts act as
        you, with only the permissions you give them. A token expires (1–90
        days), can be revoked at once, and you can have at most 10.
      </PageHero>

      <StatGrid>
        <StatTile
          label="Active tokens"
          icon={<KeyRound size={16} />}
          value={loaded ? tokens.length.toString() : "—"}
          unit={`of ${MAX_TOKENS.toString()}`}
          tone={atLimit ? "bad" : "accent"}
          hint={atLimit ? "At the limit: revoke one to add another" : undefined}
        >
          <Meter
            label="Token slots used"
            value={tokens.length / MAX_TOKENS}
            tone={atLimit ? "bad" : tokens.length >= 8 ? "warn" : "accent"}
          />
        </StatTile>
        <StatTile
          label="Expiring within a week"
          icon={<CalendarClock size={16} />}
          tone={expiringSoon ? "warn" : "good"}
          value={expiringSoon.toString()}
          hint={expiringSoon ? "Create a replacement soon" : "None soon"}
        />
        <StatTile
          label="Never used"
          icon={<Layers size={16} />}
          tone={neverUsed ? "warn" : "neutral"}
          value={neverUsed.toString()}
          hint="Revoke tokens you do not need"
          tip="A token with no recorded use is a standing permission nobody is relying on."
        />
        <StatTile
          label="Can change data"
          icon={<ShieldAlert size={16} />}
          value={canChange.toString()}
          hint="Hold a run, write or manage permission"
        />
      </StatGrid>

      <div className="dash-split">
        <Panel
          id="tok-new"
          title="New token"
          subtitle="Give it the fewest permissions the script needs."
        >
          <div className="dash-form discovery-form">
            <label>
              Name
              <input
                type="text"
                maxLength={120}
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                }}
              />
            </label>
            <label>
              Valid for (days)
              <input
                type="number"
                min={1}
                max={90}
                value={days}
                onChange={(e) => {
                  setDays(Number(e.target.value));
                }}
              />
            </label>
          </div>

          <div className="dash-chips" role="group" aria-label="Presets">
            {PRESETS.map((p) => (
              <button
                key={p.label}
                type="button"
                className="dash-chip"
                title={p.hint}
                onClick={() => {
                  setScopes(p.scopes);
                }}
              >
                {p.label}
              </button>
            ))}
          </div>

          <fieldset className="token-scopes">
            <legend>Permissions</legend>
            {SCOPES.map((scope) => (
              <label key={scope} className="discovery-check">
                <input
                  type="checkbox"
                  checked={scopes.includes(scope)}
                  onChange={() => {
                    toggle(scope);
                  }}
                />
                <span>
                  <code>{scope}</code> — {SCOPE_TEXT[scope]}
                </span>
                <Pill tone={CHANGES_DATA[scope] ? "warn" : "good"}>
                  {CHANGES_DATA[scope] ? "changes data" : "read only"}
                </Pill>
              </label>
            ))}
          </fieldset>

          {newChangesData ? (
            <p className="dash-callout is-warn">
              <ShieldAlert size={16} aria-hidden="true" />
              <span>
                This token will be able to change or delete things. Keep it out
                of shared files and shorten its lifetime.
              </span>
            </p>
          ) : null}

          <div className="copilot-actions">
            <button
              type="button"
              className="pb-btn pb-primary"
              disabled={!name.trim() || scopes.length === 0}
              onClick={create}
            >
              <KeyRound size={15} aria-hidden="true" />
              Create token
            </button>
          </div>
          {created ? (
            <div className="copilot-note" role="status">
              <p>
                Copy this token now: it is not shown again. Keep it out of
                shared files; set it as <code>URBANFLOW_TOKEN</code> for the
                Python client.
              </p>
              <div className="token-secret-row">
                <input
                  className="token-secret"
                  readOnly
                  type={revealed ? "text" : "password"}
                  value={created.token}
                  aria-label="New token secret"
                  onFocus={(e) => {
                    e.target.select();
                  }}
                />
                <button
                  type="button"
                  className="pb-btn pb-secondary"
                  aria-pressed={revealed}
                  onClick={() => {
                    setRevealed((v) => !v);
                  }}
                >
                  {revealed ? (
                    <EyeOff size={14} aria-hidden="true" />
                  ) : (
                    <Eye size={14} aria-hidden="true" />
                  )}
                  {revealed ? "Hide" : "Show"}
                </button>
                <button
                  type="button"
                  className="pb-btn pb-secondary"
                  onClick={copy}
                >
                  {copied ? (
                    <Check size={14} aria-hidden="true" />
                  ) : (
                    <Clipboard size={14} aria-hidden="true" />
                  )}
                  {copied ? "Copied" : "Copy"}
                </button>
              </div>
            </div>
          ) : null}
          {error ? (
            <p className="copilot-error" role="alert">
              {error}
            </p>
          ) : null}
        </Panel>

        <div className="copilot-side">
          <Panel
            id="tok-coverage"
            title="Permission coverage"
            subtitle="How many of your tokens hold each permission."
          >
            {tokens.length ? (
              <ul className="token-coverage">
                {SCOPES.map((scope) => (
                  <li key={scope}>
                    <span className="token-coverage__name">
                      {scope.replace(":", " · ")}
                    </span>
                    <span className="token-coverage__bar" aria-hidden="true">
                      <span
                        className={CHANGES_DATA[scope] ? "is-write" : "is-read"}
                        style={{
                          width: `${((coverage[scope] / maxCover) * 100).toFixed(0)}%`,
                        }}
                      />
                    </span>
                    <span className="token-coverage__n">
                      {coverage[scope].toString()}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyHint title="Nothing to chart yet">
                Coverage appears once you have a token.
              </EmptyHint>
            )}
          </Panel>

          <Panel id="tok-use" title="Use it from Python">
            <pre className="dash-code">
              <code>
                {
                  "export URBANFLOW_TOKEN=<your token>\n# then use the UrbanFlow Python client as usual"
                }
              </code>
            </pre>
          </Panel>
        </div>
      </div>

      <Panel id="tok-list" title="Your tokens">
        {!loaded ? (
          <div role="status" aria-label="Loading your tokens">
            <Skeleton lines={3} />
          </div>
        ) : tokens.length === 0 ? (
          <EmptyHint
            icon={<KeyRound size={22} />}
            title="You have no active tokens."
          >
            Create one above to use the Python client or your own scripts.
          </EmptyHint>
        ) : (
          <div className="dash-table-wrap comparison-table-wrap">
            <table className="dash-table copilot-table">
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">Permissions</th>
                  <th scope="col">Expires</th>
                  <th scope="col">Last used</th>
                  <th scope="col">
                    <span className="sr-only">Revoke</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {tokens.map((t) => {
                  const left = daysLeft(t.expiresAt, now);
                  return (
                    <tr key={t.id}>
                      <th scope="row">{t.name}</th>
                      <td>
                        <span className="token-scope-list">
                          {t.scopes.map((s) => (
                            <Pill
                              key={s}
                              tone={CHANGES_DATA[s] ? "warn" : "neutral"}
                            >
                              {s}
                            </Pill>
                          ))}
                        </span>
                      </td>
                      <td>
                        <div className="token-expiry">
                          <span>
                            {new Date(t.expiresAt).toLocaleDateString()}
                          </span>
                          <Meter
                            label="Lifetime remaining"
                            value={lifeLeft(t, now)}
                            tone={expiryTone(left)}
                          />
                          <span className="dash-stat__hint">
                            {left.toString()} day{left === 1 ? "" : "s"} left
                          </span>
                        </div>
                      </td>
                      <td>
                        {t.lastUsedAt
                          ? new Date(t.lastUsedAt).toLocaleString()
                          : "never"}
                      </td>
                      <td>
                        <button
                          type="button"
                          className="pb-btn pb-secondary"
                          aria-label={`Revoke ${t.name}`}
                          onClick={() => {
                            void revokeToken(t.id)
                              .then(() => {
                                setTick((n) => n + 1);
                              })
                              .catch((err: unknown) => {
                                setError(
                                  message(
                                    err,
                                    "The token could not be revoked.",
                                  ),
                                );
                              });
                          }}
                        >
                          <Trash2 size={14} aria-hidden="true" /> Revoke
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
