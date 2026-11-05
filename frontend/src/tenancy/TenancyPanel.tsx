import "../netcommon/network.css";
import { Meter, Panel, Skeleton } from "../components/dashboard/Dashboard";
import { clock, dateTime, num } from "../netcommon/format";
import { useLoad } from "../rescommon/useLoad";
import { accessMessage, getMe, getUsage } from "./api";
import type { Counters, MeResponse, UsageResponse } from "./types";

function QuotaBar({
  label,
  used,
  limit,
  detail,
}: {
  label: string;
  used: number;
  limit: number;
  detail: string;
}) {
  const fraction = limit > 0 ? used / limit : 0;
  return (
    <div className="nw-stack">
      <p className="nw-muted">
        {label}: {num(used, 0)} of {num(limit, 0)} used. {detail}
      </p>
      <Meter
        value={fraction}
        label={label}
        tone={fraction >= 0.9 ? "bad" : fraction >= 0.7 ? "warn" : "accent"}
      />
    </div>
  );
}

function Identity({ me }: { me: MeResponse }) {
  const q = me.quota;
  return (
    <div className="nw-stack">
      <ul className="nw-facts" aria-label="Identity">
        <li>Signed in as {me.identity.email || me.identity.userId}</li>
        <li>Tenant: {me.tenant.id}</li>
        <li>Role: {me.role ?? "no recognised role"}</li>
        <li>Identity provider: {me.identity.issuer}</li>
        <li>
          Token expires:{" "}
          {me.identity.tokenExpiresAt === null
            ? "Not available"
            : dateTime(
                new Date(me.identity.tokenExpiresAt * 1000).toISOString(),
              )}
        </li>
      </ul>
      <h3 className="nw-headline">Permissions</h3>
      {me.permissions.length === 0 ? (
        <p className="nw-muted">This account has no permissions.</p>
      ) : (
        <ul className="nw-legend" aria-label="Permissions">
          {me.permissions.map((p) => (
            <li key={p}>
              <span className="nw-badge is-good">{p}</span>
            </li>
          ))}
        </ul>
      )}
      <h3 className="nw-headline">Quota</h3>
      <QuotaBar
        label="Runs today"
        used={q.dailyRuns.used}
        limit={q.dailyRuns.limit}
        detail={`${num(q.dailyRuns.remaining, 0)} left; resets in ${clock(q.dailyRuns.resetsInSeconds)}.`}
      />
      <QuotaBar
        label="Runs at the same time"
        used={q.concurrentRuns.active}
        limit={q.concurrentRuns.limit}
        detail={`${num(q.concurrentRuns.remaining, 0)} free.`}
      />
      <QuotaBar
        label="Request burst (you)"
        used={q.requests.user.burst - q.requests.user.remaining}
        limit={q.requests.user.burst}
        detail={`Refills at ${num(q.requests.userPerMinute, 0)} a minute.`}
      />
      <QuotaBar
        label="Request burst (tenant)"
        used={q.requests.tenant.burst - q.requests.tenant.remaining}
        limit={q.requests.tenant.burst}
        detail={`Refills at ${num(q.requests.tenantPerMinute, 0)} a minute.`}
      />
    </div>
  );
}

function CounterRow({ name, c }: { name: string; c: Counters }) {
  return (
    <tr>
      <th scope="row">{name}</th>
      <td className="nw-num">{num(c.requestsTotal, 0)}</td>
      <td className="nw-num">{num(c.rateLimitedTotal, 0)}</td>
      <td className="nw-num">{num(c.runsToday, 0)}</td>
      <td className="nw-num">{num(c.runsTotal, 0)}</td>
      <td className="nw-num">{num(c.activeRuns, 0)}</td>
    </tr>
  );
}

function Usage({ usage }: { usage: UsageResponse }) {
  return (
    <div className="uf-table-wrap nw-scroll">
      <table className="uf-table">
        <caption>Usage on {usage.day} (UTC).</caption>
        <thead>
          <tr>
            <th scope="col">Who</th>
            <th scope="col">Requests</th>
            <th scope="col">Rate limited</th>
            <th scope="col">Runs today</th>
            <th scope="col">Runs in total</th>
            <th scope="col">Running now</th>
          </tr>
        </thead>
        <tbody>
          <CounterRow name="You" c={usage.user} />
          <CounterRow name="Whole tenant" c={usage.tenant} />
          {usage.users &&
            Object.entries(usage.users).map(([id, c]) => (
              <CounterRow key={id} name={id} c={c} />
            ))}
        </tbody>
      </table>
    </div>
  );
}

/** Account identity, role, permissions, quota bars and usage. */
export function TenancyPanel() {
  const me = useLoad(getMe, "Your account details could not be loaded.");
  const usage = useLoad(getUsage, "Usage could not be loaded.");
  return (
    <Panel
      id="res-account"
      title="Account and quota"
      subtitle="Who you are to the server, what you may do, and how much of your allowance is left."
    >
      <div className="nw-stack">
        {me.status === "loading" && <Skeleton lines={4} />}
        {me.status === "error" && (
          <p role="alert" className="nw-alert">
            {accessMessage(me.httpStatus, me.message)}
          </p>
        )}
        {me.status === "ready" && <Identity me={me.data} />}
        {usage.status === "error" && me.status === "ready" && (
          <p role="alert" className="nw-alert">
            {usage.httpStatus === 403
              ? "Your role does not include the usage:read permission, so usage is hidden."
              : accessMessage(usage.httpStatus, usage.message)}
          </p>
        )}
        {usage.status === "ready" && <Usage usage={usage.data} />}
      </div>
    </Panel>
  );
}
