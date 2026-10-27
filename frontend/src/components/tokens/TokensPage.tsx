import { useEffect, useState } from "react";
import { KeyRound, Trash2 } from "lucide-react";
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
import { ExperimentsApiError } from "../../services/v3/experiments";

const SCOPE_TEXT: Record<Scope, string> = {
  "experiments:read": "Read experiments and capabilities",
  "experiments:run": "Submit, cancel, resume and delete experiments",
  "packages:read": "Download packages",
  "packages:write": "Verify uploaded packages",
  "tokens:read": "List your tokens",
  "tokens:manage": "Revoke your tokens",
};

function message(err: unknown, fallback: string): string {
  return err instanceof ExperimentsApiError ? err.message : fallback;
}

/** Personal access tokens for the Python client and scripts. Created only
 *  here (a signed-in browser session); the secret is shown once. */
export function TokensPage() {
  const [tokens, setTokens] = useState<TokenMetadata[]>([]);
  const [name, setName] = useState("My script");
  const [scopes, setScopes] = useState<Scope[]>(["experiments:read"]);
  const [days, setDays] = useState(30);
  const [created, setCreated] = useState<CreatedToken | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    listTokens()
      .then((r) => {
        setTokens(r.tokens);
      })
      .catch((err: unknown) => {
        setError(message(err, "Your tokens could not be loaded."));
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
        setTick((n) => n + 1);
      })
      .catch((err: unknown) => {
        setError(message(err, "The token could not be created."));
      });
  };

  return (
    <div className="copilot-page">
      <header className="copilot-header">
        <p className="guided-eyebrow">Plan</p>
        <h1>API tokens</h1>
        <p>
          Personal access tokens let the Python client and your scripts act as
          you, with only the permissions you give them. A token expires (1–90
          days), can be revoked at once, and you can have at most 10.
        </p>
      </header>

      <section className="copilot-card" aria-labelledby="tok-new">
        <h2 id="tok-new">New token</h2>
        <div className="discovery-form">
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
              <code>{scope}</code> — {SCOPE_TEXT[scope]}
            </label>
          ))}
        </fieldset>
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
              Copy this token now: it is not shown again. Keep it out of shared
              files; set it as <code>URBANFLOW_TOKEN</code> for the Python
              client.
            </p>
            <input
              className="token-secret"
              readOnly
              value={created.token}
              aria-label="New token secret"
              onFocus={(e) => {
                e.target.select();
              }}
            />
          </div>
        ) : null}
        {error ? (
          <p className="copilot-error" role="alert">
            {error}
          </p>
        ) : null}
      </section>

      <section className="copilot-card" aria-labelledby="tok-list">
        <h2 id="tok-list">Your tokens</h2>
        {tokens.length === 0 ? (
          <p className="copilot-muted">You have no active tokens.</p>
        ) : (
          <div className="comparison-table-wrap">
            <table className="copilot-table">
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
                {tokens.map((t) => (
                  <tr key={t.id}>
                    <th scope="row">{t.name}</th>
                    <td>{t.scopes.join(", ")}</td>
                    <td>{new Date(t.expiresAt).toLocaleDateString()}</td>
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
                                message(err, "The token could not be revoked."),
                              );
                            });
                        }}
                      >
                        <Trash2 size={14} aria-hidden="true" /> Revoke
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
