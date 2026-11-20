import {
  Activity,
  ArrowUpRight,
  Braces,
  Check,
  ChevronRight,
  Clock3,
  FileUp,
  FlaskConical,
  ShieldAlert,
  Unplug,
} from "lucide-react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Button } from "../components/ui/button.jsx";

const metrics = [
  { label: "API endpoints", detail: "Import a specification to begin", icon: Braces },
  { label: "Request success", detail: "No requests have been tested", icon: Check },
  { label: "Avg. response time", detail: "No response data collected", icon: Clock3 },
  { label: "Recent test runs", detail: "Test execution is not active", icon: FlaskConical },
];

export default function Overview({ connectionState, onImport, onNavigate }) {
  const isConnected = connectionState === "connected";

  return (
    <div className="overview-page">
      <div className="page-heading-row">
        <div>
          <div className="page-breadcrumb"><span>Workspace</span><ChevronRight size={13} /><strong>Overview</strong></div>
          <h1>API health overview</h1>
          <p className="page-description">Your contract quality and runtime reliability, in one place.</p>
        </div>
        <Button className="import-button" onClick={onImport}><FileUp size={15} /> Import API specification</Button>
      </div>

      <section className={`service-banner ${isConnected ? "service-banner-connected" : "service-banner-offline"}`} aria-label="API connection status">
        <span className="service-icon"><Activity size={17} /></span>
        <div className="service-copy">
          <strong>ContractIQ API</strong>
          <span>{isConnected ? "The backend is reachable and responding." : connectionState === "loading" ? "Checking the local backend connection…" : "The backend could not be reached. Check the API server and retry."}</span>
        </div>
        <span className="service-spacer" />
        <span className="service-status"><i />{isConnected ? "Connected" : connectionState === "loading" ? "Checking" : "Disconnected"}</span>
      </section>

      <section className="metrics-grid" aria-label="API health metrics">
        {metrics.map(({ label, detail, icon: Icon }) => (
          <article className="metric-panel" key={label}>
            <div className="metric-topline"><span>{label}</span><Icon size={15} strokeWidth={1.7} /></div>
            <div className="metric-value" aria-label="No data">—</div>
            <p>{detail}</p>
          </article>
        ))}
      </section>

      <section className="chart-panel" aria-labelledby="trend-title">
        <div className="panel-heading chart-panel-heading">
          <div><span className="section-overline">PERFORMANCE</span><h2 id="trend-title">API performance trends</h2></div>
          <span className="chart-period">No time range · no data</span>
        </div>
        <div className="chart-plot" role="img" aria-label="Empty API performance trend chart. No API response data is available.">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={[]} margin={{ top: 14, right: 12, bottom: 0, left: -18 }}>
              <defs>
                <linearGradient id="responseFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#8ba4c9" stopOpacity={0.18} />
                  <stop offset="96%" stopColor="#8ba4c9" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#282d35" strokeDasharray="3 5" vertical={false} />
              <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fill: "#777e89", fontSize: 10 }} />
              <YAxis axisLine={false} tickLine={false} tick={{ fill: "#777e89", fontSize: 10 }} />
              <Tooltip contentStyle={{ background: "#191d24", border: "1px solid #343943", borderRadius: 6, color: "#e6e8ed" }} />
              <Area type="monotone" dataKey="latency" stroke="#8ba4c9" fill="url(#responseFill)" />
            </AreaChart>
          </ResponsiveContainer>
          <div className="chart-empty-overlay">
            <span className="empty-chart-icon"><Activity size={16} /></span>
            <strong>Waiting for API traffic</strong>
            <span>Performance trends appear after an API is connected and monitored.</span>
          </div>
        </div>
        <div className="chart-legend"><span><i className="legend-line" /> Response latency</span><span className="legend-unavailable">No telemetry collected</span></div>
      </section>

      <div className="activity-grid">
        <section className="data-panel" aria-labelledby="runs-title">
          <div className="panel-heading">
            <div><span className="section-overline">VALIDATION</span><h2 id="runs-title">Recent test executions</h2></div>
            <Button className="panel-link" variant="ghost" size="sm" aria-label="Open test runs" onClick={() => onNavigate("testRuns")}>View all <ArrowUpRight size={13} /></Button>
          </div>
          <div className="table-scroll">
            <table className="data-table">
              <thead><tr><th>TEST RUN</th><th>STATUS</th><th>STARTED</th></tr></thead>
              <tbody><tr><td className="table-empty" colSpan="3"><span className="table-empty-icon"><FlaskConical size={17} /></span><strong>No test runs yet</strong><span>API checks will appear here when testing is available.</span></td></tr></tbody>
            </table>
          </div>
        </section>

        <section className="data-panel" aria-labelledby="changes-title">
          <div className="panel-heading">
            <div><span className="section-overline">CONTRACT HEALTH</span><h2 id="changes-title">Recent failures & changes</h2></div>
            <Button className="panel-link" variant="ghost" size="sm" aria-label="Open contract changes" onClick={() => onNavigate("changes")}>View all <ArrowUpRight size={13} /></Button>
          </div>
          <div className="activity-empty">
            <span className="table-empty-icon"><ShieldAlert size={17} /></span>
            <strong>No failures or changes</strong>
            <span>Connect an API to surface contract changes and request failures.</span>
          </div>
        </section>
      </div>

      <section className="setup-strip">
        <span className="setup-strip-icon"><Unplug size={16} /></span>
        <div><strong>Start with an API specification</strong><span>Import your contract to make endpoints, test runs, and performance insights available.</span></div>
        <Button className="setup-strip-action" variant="secondary" size="sm" onClick={onImport}>Import specification <ChevronRight size={14} /></Button>
      </section>
    </div>
  );
}