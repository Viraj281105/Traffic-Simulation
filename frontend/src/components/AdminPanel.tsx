import { useEffect, useState, useCallback } from "react";
import { get } from "../services/api";
import { Users, RefreshCw, Search } from "lucide-react";
import { StatusState } from "./ui/StatusState";
import "./AdminPanel.css";

interface UserRow {
  sub: string;
  email: string;
  username: string;
  firstSeen: string | null;
  lastSeen: string | null;
  runCount: number;
}

interface UsersResponse {
  users: UserRow[];
  count: number;
}

function formatRelative(isoString: string | null): string {
  if (!isoString) return "—";
  const date = new Date(isoString.endsWith("Z") ? isoString : isoString + "Z");
  const diffMs = Date.now() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${String(diffMin)}m ago`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `${String(diffH)}h ago`;
  const diffD = Math.floor(diffH / 24);
  if (diffD < 30) return `${String(diffD)}d ago`;
  return date.toLocaleDateString();
}

function formatDateTime(isoString: string | null): string {
  if (!isoString) return "—";
  const date = new Date(isoString.endsWith("Z") ? isoString : isoString + "Z");
  return date.toLocaleString();
}

export function AdminPanel() {
  const [users, setUsers] = useState<UserRow[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    get<UsersResponse>("/api/users")
      .then((data) => {
        setUsers(data.users);
        setCount(data.count);
        setLoading(false);
      })
      .catch((e: unknown) => {
        const msg = e instanceof Error ? e.message : String(e);
        setError(msg);
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      load();
    }, 0);
    return () => {
      clearTimeout(timer);
    };
  }, [load]);

  const filtered = users.filter((u) => {
    const q = query.toLowerCase();
    return (
      !q ||
      u.email.toLowerCase().includes(q) ||
      u.username.toLowerCase().includes(q) ||
      u.sub.toLowerCase().includes(q)
    );
  });

  const loaded = !loading && !error;

  return (
    <div className="guided-page admin-panel">
      <header className="guided-intro admin-panel__intro">
        <div>
          <p className="guided-eyebrow">Admin</p>
          <h1>Admin Panel</h1>
          <p>Registered users from your Cognito user pool.</p>
        </div>
        {loaded && (
          <span className="uf-badge admin-panel__count">
            <Users size={13} aria-hidden="true" />
            {count.toString()} total {count === 1 ? "user" : "users"}
          </span>
        )}
      </header>

      <section className="uf-panel admin-panel__body" aria-label="Users">
        <div className="admin-panel__toolbar">
          <div className="admin-panel__search-wrap">
            <Search
              size={15}
              className="admin-panel__search-icon"
              aria-hidden="true"
            />
            <input
              id="admin-user-search"
              type="search"
              className="uf-input admin-panel__search"
              placeholder="Search by email or username…"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
              }}
              aria-label="Search users"
            />
          </div>
          <button
            type="button"
            className={`pb-btn pb-secondary admin-panel__refresh${loading ? " is-spinning" : ""}`}
            onClick={load}
            disabled={loading}
            aria-label="Refresh user list"
            title="Refresh"
          >
            <RefreshCw size={15} aria-hidden="true" />
            {loading ? "Loading…" : "Refresh"}
          </button>
        </div>

        {error ? (
          <StatusState
            tone="error"
            role="alert"
            compact
            title="Could not load users"
            actions={
              <button
                type="button"
                className="pb-btn pb-secondary pb-sm"
                onClick={load}
              >
                Try again
              </button>
            }
          >
            {error}
          </StatusState>
        ) : loading && users.length === 0 ? (
          <div className="admin-panel__skeleton-rows" aria-hidden="true">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="admin-panel__skeleton-row" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <StatusState tone="empty" compact title="No users to show">
            {query
              ? "No users match your search."
              : "No users have logged in yet."}
          </StatusState>
        ) : (
          <div className="uf-table-wrap">
            <table className="uf-table" aria-label="User registry">
              <thead>
                <tr>
                  <th scope="col" className="is-num">
                    #
                  </th>
                  <th scope="col">Email</th>
                  <th scope="col">Username</th>
                  <th scope="col" className="is-num">
                    Runs
                  </th>
                  <th scope="col">First seen</th>
                  <th scope="col">Last seen</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((user, idx) => (
                  <tr key={user.sub}>
                    <td className="is-num admin-panel__td-index">{idx + 1}</td>
                    <td>
                      <span className="admin-panel__email">
                        {user.email || "—"}
                      </span>
                    </td>
                    <td>
                      <span className="admin-panel__username">
                        {user.username}
                      </span>
                    </td>
                    <td className="is-num">
                      <span
                        className={`admin-panel__run-badge${user.runCount > 0 ? " has-runs" : ""}`}
                      >
                        {user.runCount}
                      </span>
                    </td>
                    <td title={formatDateTime(user.firstSeen)}>
                      {formatRelative(user.firstSeen)}
                    </td>
                    <td title={formatDateTime(user.lastSeen)}>
                      {formatRelative(user.lastSeen)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <p className="uf-hint admin-panel__footer-note">
        Users are automatically recorded on first login. Passwords are never
        stored here — they stay in Cognito.
      </p>
    </div>
  );
}
