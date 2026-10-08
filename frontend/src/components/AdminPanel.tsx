import { useEffect, useState, useCallback } from "react";
import { get } from "../services/api";
import { Users, RefreshCw, Search, ShieldCheck, Activity } from "lucide-react";
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

  return (
    <div className="admin-panel">
      {/* ── Header ─────────────────────────────────────────────────── */}
      <div className="admin-panel__hero">
        <div className="admin-panel__hero-icon">
          <ShieldCheck size={32} aria-hidden="true" />
        </div>
        <div>
          <h1 className="admin-panel__title">Admin Panel</h1>
          <p className="admin-panel__subtitle">
            Registered users from your Cognito user pool
          </p>
        </div>
        <div className="admin-panel__stat-pill">
          <Activity size={14} aria-hidden="true" />
          <strong>{count}</strong> total users
        </div>
      </div>

      {/* ── Toolbar ────────────────────────────────────────────────── */}
      <div className="admin-panel__toolbar">
        <div className="admin-panel__search-wrap">
          <Search size={15} className="admin-panel__search-icon" aria-hidden="true" />
          <input
            id="admin-user-search"
            type="search"
            className="admin-panel__search"
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
          className={`admin-panel__refresh ${loading ? "is-spinning" : ""}`}
          onClick={load}
          disabled={loading}
          aria-label="Refresh user list"
          title="Refresh"
        >
          <RefreshCw size={15} aria-hidden="true" />
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>

      {/* ── Error state ─────────────────────────────────────────────── */}
      {error && (
        <div className="admin-panel__error" role="alert">
          <strong>Could not load users:</strong> {error}
        </div>
      )}

      {/* ── Table ───────────────────────────────────────────────────── */}
      {!error && (
        <div className="admin-panel__table-wrap">
          {loading && users.length === 0 ? (
            <div className="admin-panel__skeleton-rows">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="admin-panel__skeleton-row" />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <div className="admin-panel__empty">
              <Users size={40} className="admin-panel__empty-icon" aria-hidden="true" />
              <p>{query ? "No users match your search." : "No users have logged in yet."}</p>
            </div>
          ) : (
            <table className="admin-panel__table" aria-label="User registry">
              <thead>
                <tr>
                  <th scope="col">#</th>
                  <th scope="col">Email</th>
                  <th scope="col">Username</th>
                  <th scope="col">Runs</th>
                  <th scope="col">First seen</th>
                  <th scope="col">Last seen</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((user, idx) => (
                  <tr key={user.sub}>
                    <td className="admin-panel__td-index">{idx + 1}</td>
                    <td>
                      <span className="admin-panel__email">{user.email || "—"}</span>
                    </td>
                    <td>
                      <span className="admin-panel__username">{user.username}</span>
                    </td>
                    <td>
                      <span className={`admin-panel__run-badge ${user.runCount > 0 ? "has-runs" : ""}`}>
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
          )}
        </div>
      )}

      {/* ── Footer ─────────────────────────────────────────────────── */}
      <p className="admin-panel__footer-note">
        Users are automatically recorded on first login. Passwords are never stored here
        — they stay in Cognito.
      </p>
    </div>
  );
}
