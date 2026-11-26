import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Bot,
  Check,
  CircleAlert,
  Pause,
  Play,
  Radio,
  RefreshCw,
  Trash2,
  Wifi,
  WifiOff,
} from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Button } from "../components/ui/button.jsx";
import {
  acknowledgeAnomaly,
  createMonitoringConfiguration,
  createMonitoringSocket,
  deleteMonitoringConfiguration,
  getAnomalyModelStatus,
  getMonitoringAlerts,
  getMonitoringAnomalies,
  getMonitoringConfigurations,
  getMonitoringErrors,
  getMonitoringMetrics,
  getMonitoringOverview,
  getProjectSpecifications,
  getSpecificationEndpoints,
  pauseMonitoringConfiguration,
  refreshAuthSession,
  startMonitoringConfiguration,
  trainAnomalyModel,
  updateMonitoringAlert,
} from "../services/api.js";

const SECTION_INFO = {
  monitoring: {
    title: "Monitoring",
    description: "Configure safe, scheduled probes and review current API health.",
  },
  performance: {
    title: "Performance",
    description: "Explore measured probe latency and availability over time.",
  },
  errors: {
    title: "Errors",
    description: "Investigate failed probes and contract validation errors.",
  },
  insights: {
    title: "AI Insights",
    description: "Review Isolation Forest outliers and rule-based warm-up findings.",
  },
  live: {
    title: "Live Monitoring",
    description: "Receive project-scoped alert events over a live WebSocket.",
  },
  alerts: {
    title: "Alerts",
    description: "Read, acknowledge, and resolve persistent monitoring alerts.",
  },
};

const EMPTY_METRICS = {
  summary: {},
  series: [],
  endpoints: [],
  total_checks: 0,
};

function formatNumber(value, suffix = "") {
  return value === null || value === undefined ? "—" : `${Number(value).toLocaleString()}${suffix}`;
}

function formatTime(value) {
  return value ? new Date(value).toLocaleString() : "—";
}

function MetricCard({ label, value, note, tone }) {
  return (
    <div className={`monitor-metric ${tone || ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      {note && <small>{note}</small>}
    </div>
  );
}

function EndpointLabel({ method, endpoint }) {
  return <span className="monitor-endpoint"><b>{method}</b><code>{endpoint}</code></span>;
}

export default function MonitoringPage({ section, projectId }) {
  const [windowSize, setWindowSize] = useState("1h");
  const [environmentName, setEnvironmentName] = useState("");
  const [overview, setOverview] = useState(null);
  const [metrics, setMetrics] = useState(EMPTY_METRICS);
  const [configurations, setConfigurations] = useState([]);
  const [errors, setErrors] = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [model, setModel] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [specifications, setSpecifications] = useState([]);
  const [selectedSpecification, setSelectedSpecification] = useState("");
  const [endpoints, setEndpoints] = useState([]);
  const [selectedEndpointIds, setSelectedEndpointIds] = useState([]);
  const [form, setForm] = useState({
    name: "",
    environment_name: "development",
    base_url: "",
    interval_seconds: "60",
    timeout_seconds: "10",
  });
  const [liveEvents, setLiveEvents] = useState([]);
  const [liveStatus, setLiveStatus] = useState("disconnected");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const pageInfo = SECTION_INFO[section] || SECTION_INFO.monitoring;
  const environments = useMemo(
    () => [...new Set(configurations.map((item) => item.environment_name).filter(Boolean))].sort(),
    [configurations],
  );
  const safeEndpoints = useMemo(
    () => endpoints.filter((endpoint) =>
      ["GET", "HEAD", "OPTIONS"].includes(String(endpoint.method).toUpperCase())
      && !(endpoint.security || []).length
    ),
    [endpoints],
  );

  useEffect(() => {
    setOverview(null);
    setMetrics(EMPTY_METRICS);
    setConfigurations([]);
    setErrors([]);
    setAnomalies([]);
    setModel(null);
    setAlerts([]);
    setUnreadCount(0);
    setError("");
    setNotice("");
    if (!projectId || !["monitoring", "performance", "errors", "insights", "alerts"].includes(section)) {
      setLoading(false);
      return undefined;
    }

    let active = true;
    async function load() {
      setLoading(true);
      setError("");
      try {
        if (section === "monitoring") {
          const [current, configs] = await Promise.all([
            getMonitoringOverview(projectId, windowSize, environmentName),
            getMonitoringConfigurations(projectId),
          ]);
          if (!active) return;
          setOverview(current);
          setMetrics(current.metrics || EMPTY_METRICS);
          setConfigurations(configs);
        } else if (section === "performance") {
          const [result, configs] = await Promise.all([
            getMonitoringMetrics(projectId, windowSize, "", environmentName),
            getMonitoringConfigurations(projectId),
          ]);
          if (!active) return;
          setMetrics(result);
          setConfigurations(configs);
        } else if (section === "errors") {
          const [result, configs] = await Promise.all([
            getMonitoringErrors(projectId, { page: 1, page_size: 100, environment_name: environmentName }),
            getMonitoringConfigurations(projectId),
          ]);
          if (!active) return;
          setErrors(result.items || []);
          setConfigurations(configs);
        } else if (section === "insights") {
          const [detectionResult, modelResult] = await Promise.all([
            getMonitoringAnomalies(projectId, { page: 1, page_size: 100 }),
            getAnomalyModelStatus(projectId),
          ]);
          if (!active) return;
          setAnomalies(detectionResult.items || []);
          setModel(modelResult);
        } else if (section === "alerts") {
          const result = await getMonitoringAlerts(projectId, { page: 1, page_size: 100 });
          if (!active) return;
          setAlerts(result.items || []);
          setUnreadCount(result.unread_count || 0);
        }
      } catch (caught) {
        if (active) setError(caught.message);
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    const timer = window.setInterval(() => { void load(); }, 30000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [projectId, section, windowSize, environmentName]);

  useEffect(() => {
    if (!projectId || section !== "monitoring") {
      setSpecifications([]);
      setEndpoints([]);
      setSelectedSpecification("");
      setSelectedEndpointIds([]);
      return undefined;
    }
    let active = true;
    getProjectSpecifications(projectId)
      .then((items) => {
        if (!active) return;
        setSpecifications(items);
        setSelectedSpecification((current) =>
          items.some((item) => item.id === current) ? current : items[0]?.id || ""
        );
      })
      .catch((caught) => { if (active) setError(caught.message); });
    return () => { active = false; };
  }, [projectId, section]);

  useEffect(() => {
    if (!selectedSpecification || section !== "monitoring") {
      setEndpoints([]);
      setSelectedEndpointIds([]);
      return undefined;
    }
    let active = true;
    getSpecificationEndpoints(selectedSpecification)
      .then((items) => {
        if (!active) return;
        setEndpoints(items);
        setSelectedEndpointIds((current) => current.filter((id) => items.some((item) => item.id === id)));
      })
      .catch((caught) => { if (active) setError(caught.message); });
    return () => { active = false; };
  }, [selectedSpecification, section]);

  useEffect(() => {
    if (!projectId || section !== "live") {
      setLiveStatus("disconnected");
      return undefined;
    }
    let active = true;
    let socket;
    let reconnectTimer;
    function connect() {
      try {
        socket = createMonitoringSocket(projectId);
      } catch (caught) {
        setError(caught.message);
        setLiveStatus("disconnected");
        return;
      }
      socket.onopen = () => {
        if (active) setLiveStatus("connected");
      };
      socket.onmessage = (event) => {
        if (!active) return;
        try {
          const payload = JSON.parse(event.data);
          if (payload.event === "HEARTBEAT") {
            socket.send("PING");
            return;
          }
          if (payload.event !== "PONG") {
            setLiveEvents((current) => [payload, ...current].slice(0, 100));
          }
        } catch {
          setError("The live monitoring stream sent an invalid event.");
        }
      };
      socket.onerror = () => {
        if (active) setLiveStatus("disconnected");
      };
      socket.onclose = (event) => {
        if (!active) return;
        if (event.code === 4401) {
          setLiveStatus("reconnecting");
          refreshAuthSession()
            .then((session) => {
              if (!active) return;
              if (session) connect();
              else window.dispatchEvent(new Event("contractiq:auth-expired"));
            })
            .catch((caught) => {
              if (!active) return;
              setError(caught.message);
              reconnectTimer = window.setTimeout(connect, 5000);
            });
          return;
        }
        if (event.code === 4403 || event.code === 4404) {
          setLiveStatus("disconnected");
          setError("Access to this live project stream was denied.");
          return;
        }
        setLiveStatus("reconnecting");
        reconnectTimer = window.setTimeout(connect, 2000);
      };
    }
    connect();
    return () => {
      active = false;
      window.clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [projectId, section]);

  const refreshMonitoring = useCallback(async () => {
    if (!projectId) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const [current, configs] = await Promise.all([
        getMonitoringOverview(projectId, windowSize, environmentName),
        getMonitoringConfigurations(projectId),
      ]);
      setOverview(current);
      setMetrics(current.metrics || EMPTY_METRICS);
      setConfigurations(configs);
    } catch (caught) {
      setError(caught.message);
    } finally {
      setBusy(false);
    }
  }, [projectId, windowSize, environmentName]);

  useEffect(() => {
    setEnvironmentName("");
  }, [projectId]);

  async function createConfiguration(event) {
    event.preventDefault();
    if (!selectedSpecification || selectedEndpointIds.length === 0) {
      setError("Select an API specification and at least one safe endpoint.");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await createMonitoringConfiguration(projectId, {
        specification_id: selectedSpecification,
        name: form.name,
        environment_name: form.environment_name,
        base_url: form.base_url,
        endpoint_ids: selectedEndpointIds,
        interval_seconds: Number(form.interval_seconds),
        timeout_seconds: Number(form.timeout_seconds),
      });
      setForm((current) => ({ ...current, name: "" }));
      await refreshMonitoring();
      setNotice("Configuration saved. Start it when you are ready to begin scheduled probes.");
    } catch (caught) {
      setError(caught.message);
    } finally {
      setBusy(false);
    }
  }

  async function changeConfiguration(configuration, action) {
    if (action === "delete" && !window.confirm(`Delete "${configuration.name}" and its stored checks?`)) return;
    setBusy(true);
    setError("");
    try {
      if (action === "start") await startMonitoringConfiguration(projectId, configuration.id);
      else if (action === "pause") await pauseMonitoringConfiguration(projectId, configuration.id);
      else await deleteMonitoringConfiguration(projectId, configuration.id);
      await refreshMonitoring();
    } catch (caught) {
      setError(caught.message);
    } finally {
      setBusy(false);
    }
  }

  async function trainModel() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await trainAnomalyModel(projectId);
      setModel(result);
      setNotice(result.message || "Anomaly model status updated.");
    } catch (caught) {
      setError(caught.message);
    } finally {
      setBusy(false);
    }
  }

  async function acknowledge(anomaly) {
    try {
      await acknowledgeAnomaly(projectId, anomaly.id);
      setAnomalies((current) => current.map((item) =>
        item.id === anomaly.id ? { ...item, acknowledged: true } : item
      ));
    } catch (caught) {
      setError(caught.message);
    }
  }

  async function refreshErrors() {
    setBusy(true);
    setError("");
    try {
      const result = await getMonitoringErrors(projectId, {
        page: 1,
        page_size: 100,
        environment_name: environmentName,
      });
      setErrors(result.items || []);
    } catch (caught) {
      setError(caught.message);
    } finally {
      setBusy(false);
    }
  }

  async function updateAlert(alert, action) {
    try {
      const updated = await updateMonitoringAlert(projectId, alert.id, action);
      setAlerts((current) => current.map((item) => item.id === alert.id ? updated : item));
      if (action === "read" && !alert.read_at) setUnreadCount((count) => Math.max(0, count - 1));
      if (action === "resolve" && !alert.read_at) setUnreadCount((count) => Math.max(0, count - 1));
    } catch (caught) {
      setError(caught.message);
    }
  }

  const metricSummary = metrics.summary || {};
  const latestCheck = overview?.latest_check;

  return (
    <div className="placeholder-page monitoring-page">
      <div className="page-heading-row">
        <div>
          <div className="page-breadcrumb"><span>Workspace</span><span className="breadcrumb-slash">/</span><strong>{pageInfo.title}</strong></div>
          <h1>{pageInfo.title}</h1>
          <p className="page-description">{pageInfo.description}</p>
        </div>
        {["monitoring", "performance", "errors"].includes(section) && (
          <div className="monitor-filters">
            {["monitoring", "performance"].includes(section) && <label className="monitor-window">Window
              <select value={windowSize} onChange={(event) => setWindowSize(event.target.value)}>
                <option value="5m">Last 5 minutes</option>
                <option value="15m">Last 15 minutes</option>
                <option value="1h">Last hour</option>
                <option value="24h">Last 24 hours</option>
                <option value="7d">Last 7 days</option>
              </select>
            </label>}
            <label className="monitor-window">Environment
              <select value={environmentName} onChange={(event) => setEnvironmentName(event.target.value)}>
                <option value="">All environments</option>
                {environments.map((environment) => <option key={environment} value={environment}>{environment}</option>)}
              </select>
            </label>
          </div>
        )}
      </div>
      {!projectId && <div className="stage-empty"><Activity size={22} /><strong>Select a project</strong><span>Choose an API project from the workspace selector to view monitoring data.</span></div>}
      {error && <div className="stage-error" role="alert">{error}</div>}
      {notice && <div className="monitor-notice" role="status">{notice}</div>}
      {projectId && loading && <div className="stage-state">Loading monitoring data...</div>}

      {projectId && !loading && section === "monitoring" && (
        <>
          <div className="monitor-cards">
            <MetricCard label="Probe checks" value={formatNumber(metricSummary.probe_count)} note={`${metrics.sampled_checks || 0} samples in ${windowSize}`} />
            <MetricCard label="Availability" value={formatNumber(metricSummary.success_rate, "%")} tone="success" />
            <MetricCard label="Average latency" value={formatNumber(metricSummary.average_latency_ms, " ms")} />
            <MetricCard label="Active alerts" value={formatNumber(overview?.active_alerts)} tone={overview?.active_alerts ? "warning" : ""} />
          </div>
          <section className="stage-panel monitor-config-form">
            <div className="stage-toolbar"><div><strong>Create a monitoring configuration</strong><span>Only public GET, HEAD, or OPTIONS operations are scheduled.</span></div></div>
            <form onSubmit={createConfiguration}>
              <div className="monitor-form-grid">
                <label>Name<input required maxLength="120" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Public API production" /></label>
                <label>Environment<input required maxLength="100" value={form.environment_name} onChange={(event) => setForm({ ...form, environment_name: event.target.value })} /></label>
                <label>API base URL<input required type="url" value={form.base_url} onChange={(event) => setForm({ ...form, base_url: event.target.value })} placeholder="https://api.example.com" /></label>
                <label>Specification<select value={selectedSpecification} onChange={(event) => setSelectedSpecification(event.target.value)}><option value="">Select specification</option>{specifications.map((specification) => <option key={specification.id} value={specification.id}>v{specification.version_number} · {specification.title}</option>)}</select></label>
                <label>Interval (seconds)<input type="number" min="30" max="3600" value={form.interval_seconds} onChange={(event) => setForm({ ...form, interval_seconds: event.target.value })} /></label>
                <label>Timeout (seconds)<input type="number" min="1" max="30" step="0.5" value={form.timeout_seconds} onChange={(event) => setForm({ ...form, timeout_seconds: event.target.value })} /></label>
              </div>
              <div className="monitor-endpoint-picker">
                <div><strong>Safe endpoints</strong><span>{safeEndpoints.length} eligible operations · write methods and authenticated operations are excluded</span></div>
                {safeEndpoints.length === 0 ? <p className="monitor-muted">Select a specification with public GET, HEAD, or OPTIONS endpoints.</p> : (
                  <div className="monitor-endpoint-options">{safeEndpoints.map((endpoint) => (
                    <label key={endpoint.id}>
                      <input
                        type="checkbox"
                        checked={selectedEndpointIds.includes(endpoint.id)}
                        onChange={(event) => setSelectedEndpointIds((current) =>
                          event.target.checked
                            ? [...current, endpoint.id]
                            : current.filter((id) => id !== endpoint.id)
                        )}
                      />
                      <EndpointLabel method={endpoint.method} endpoint={endpoint.path} />
                    </label>
                  ))}</div>
                )}
              </div>
              <div className="monitor-form-actions">
                <span>Targets must pass the backend's exact host/port allowlist and DNS safety checks.</span>
                <Button type="submit" disabled={busy || safeEndpoints.length === 0}>Save configuration</Button>
              </div>
            </form>
          </section>
          <section className="stage-panel monitor-config-list">
            <div className="stage-toolbar"><div><strong>Monitoring configurations</strong><span>{configurations.length} saved configurations · latest result {latestCheck ? formatTime(latestCheck.checked_at) : "not yet available"}</span></div><Button variant="ghost" size="sm" onClick={refreshMonitoring} disabled={busy}><RefreshCw size={13} /> Refresh</Button></div>
            {configurations.length === 0 ? <div className="stage-state">No monitoring configurations have been created.</div> : configurations.map((configuration) => (
              <div className="monitor-config-row" key={configuration.id}>
                <div><strong>{configuration.name}</strong><span>{configuration.environment_name} · {configuration.endpoint_ids.length} endpoints · every {configuration.interval_seconds}s</span><small>{configuration.base_url}</small></div>
                <span className={`monitor-state ${configuration.enabled ? "is-running" : ""}`}>{configuration.enabled ? "RUNNING" : "PAUSED"}</span>
                <div className="monitor-row-actions">
                  {configuration.enabled
                    ? <Button variant="outline" size="sm" disabled={busy} onClick={() => changeConfiguration(configuration, "pause")}><Pause size={13} /> Pause</Button>
                    : <Button variant="outline" size="sm" disabled={busy} onClick={() => changeConfiguration(configuration, "start")}><Play size={13} /> Start</Button>}
                  <Button variant="ghost" size="icon" aria-label="Delete configuration" disabled={busy} onClick={() => changeConfiguration(configuration, "delete")}><Trash2 size={14} /></Button>
                </div>
              </div>
            ))}
          </section>
        </>
      )}

      {projectId && !loading && section === "performance" && (
        <>
          <div className="monitor-cards">
            <MetricCard label="Probes" value={formatNumber(metricSummary.probe_count)} note={metrics.sample_truncated ? "Recent sample capped at 20,000 rows" : "Measured scheduled probes"} />
            <MetricCard label="Availability" value={formatNumber(metricSummary.success_rate, "%")} tone="success" />
            <MetricCard label="P95 latency" value={formatNumber(metricSummary.p95_latency_ms, " ms")} />
            <MetricCard label="P99 latency" value={formatNumber(metricSummary.p99_latency_ms, " ms")} />
          </div>
          <section className="stage-panel monitor-chart-panel">
            <div className="stage-toolbar"><div><strong>Latency trend</strong><span>Measured HTTP probe completion time; traffic volume is not inferred from probes.</span></div></div>
            {metrics.series?.length ? <div className="monitor-chart"><ResponsiveContainer width="100%" height="100%">
              <LineChart data={metrics.series} margin={{ top: 12, right: 16, bottom: 4, left: 0 }}>
                <CartesianGrid stroke="#292f39" strokeDasharray="3 3" />
                <XAxis dataKey="timestamp" tickFormatter={(value) => new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} stroke="#6f7885" tick={{ fontSize: 9 }} />
                <YAxis yAxisId="latency" stroke="#7f8a99" tick={{ fontSize: 9 }} />
                <Tooltip labelFormatter={(value) => formatTime(value)} contentStyle={{ background: "#15191f", border: "1px solid #343a44", borderRadius: 5, fontSize: 10 }} />
                <Line yAxisId="latency" type="monotone" dataKey="average_latency_ms" name="Average ms" stroke="#9eb4d2" strokeWidth={2} dot={false} connectNulls />
                <Line yAxisId="latency" type="monotone" dataKey="p95_latency_ms" name="P95 ms" stroke="#d7a674" strokeWidth={1.5} dot={false} connectNulls />
              </LineChart>
            </ResponsiveContainer></div> : <div className="stage-state">No monitoring samples are available for this time window.</div>}
          </section>
          <section className="stage-panel monitor-table-panel">
            <div className="stage-toolbar"><div><strong>Endpoint performance</strong><span>Latency and availability are calculated from stored checks.</span></div></div>
            <div className="table-scroll"><table className="data-table stage-table"><thead><tr><th>ENDPOINT</th><th>PROBES</th><th>AVAILABILITY</th><th>AVG LATENCY</th><th>P95</th><th>FAILURES</th></tr></thead><tbody>
              {(metrics.endpoints || []).map((item) => <tr key={`${item.method}:${item.endpoint}`}><td><EndpointLabel method={item.method} endpoint={item.endpoint} /></td><td>{item.probe_count}</td><td>{formatNumber(item.success_rate, "%")}</td><td>{formatNumber(item.average_latency_ms, " ms")}</td><td>{formatNumber(item.p95_latency_ms, " ms")}</td><td>{item.failed_probes}</td></tr>)}
              {!metrics.endpoints?.length && <tr><td className="table-empty" colSpan="6">No endpoint measurements in this window.</td></tr>}
            </tbody></table></div>
          </section>
        </>
      )}

      {projectId && !loading && section === "errors" && (
        <section className="stage-panel monitor-table-panel">
          <div className="stage-toolbar"><div><strong>Failed monitoring checks</strong><span>{errors.length} recent failures · check records never include response bodies or headers</span></div><Button variant="ghost" size="sm" onClick={refreshErrors} disabled={busy}><RefreshCw size={13} /> Refresh</Button></div>
          <div className="table-scroll"><table className="data-table stage-table"><thead><tr><th>WHEN</th><th>ENDPOINT</th><th>CATEGORY</th><th>STATUS</th><th>LATENCY</th><th>DETAIL</th></tr></thead><tbody>
            {errors.map((item) => <tr key={item.id}><td>{formatTime(item.checked_at)}</td><td><EndpointLabel method={item.method} endpoint={item.endpoint} /></td><td><span className="severity-badge severity-high">{item.error_category || "UNKNOWN"}</span></td><td>{item.status_code || "—"}</td><td>{formatNumber(item.latency_ms, " ms")}</td><td>{item.error_message || "No additional detail"}</td></tr>)}
            {!errors.length && <tr><td className="table-empty" colSpan="6">No failed checks have been recorded.</td></tr>}
          </tbody></table></div>
        </section>
      )}

      {projectId && !loading && section === "insights" && (
        <>
          <section className="stage-panel model-status-panel">
            <div className="model-status-icon"><Bot size={19} /></div>
            <div className="model-status-copy"><strong>{model?.model_status || "WARMING_UP"}</strong><span>{model?.message || "Rule-based detection is active until enough real monitoring checks are collected."}</span><small>{model?.available_samples || model?.training_samples || 0} monitoring samples · {model?.minimum_training_samples || 100} required · scores are not probabilities</small></div>
            <Button variant="outline" disabled={busy} onClick={trainModel}><RefreshCw size={13} /> Train / refresh model</Button>
          </section>
          <section className="stage-panel monitor-table-panel">
            <div className="stage-toolbar"><div><strong>Detected anomalies</strong><span>Explanations are deterministic summaries of the measured baseline and current checks.</span></div></div>
            <div className="monitor-anomaly-list">
              {anomalies.map((anomaly) => <article className="monitor-anomaly" key={anomaly.id}>
                <div className="monitor-anomaly-heading"><span className={`severity-badge severity-${anomaly.severity.toLowerCase()}`}>{anomaly.severity}</span><strong>{anomaly.anomaly_type.replaceAll("_", " ")}</strong><small>{formatTime(anomaly.detected_at)}</small></div>
                <EndpointLabel method={anomaly.method} endpoint={anomaly.endpoint} />
                <p>{anomaly.explanation}</p>
                <div className="monitor-anomaly-meta"><span>{anomaly.detection_method}</span><span>Isolation score: {Number(anomaly.anomaly_score).toFixed(4)} · not a probability</span></div>
                <div className="monitor-recommendation">{anomaly.recommendation}</div>
                {!anomaly.acknowledged && <Button variant="ghost" size="sm" onClick={() => acknowledge(anomaly)}><Check size={13} /> Acknowledge</Button>}
              </article>)}
              {!anomalies.length && <div className="stage-state">No anomalies have been detected from stored measurements.</div>}
            </div>
          </section>
        </>
      )}

      {projectId && section === "live" && (
        <section className="stage-panel live-monitor-panel">
          <div className="stage-toolbar"><div><strong>Project alert stream</strong><span>WebSocket delivery is process-local; use one backend worker for live events.</span></div>
            <span className={`live-connection ${liveStatus}`}><i />{liveStatus === "connected" ? <Wifi size={13} /> : <WifiOff size={13} />}{liveStatus}</span>
          </div>
          {error && <p className="monitor-live-error">{error}</p>}
          <div className="monitor-live-feed">
            {liveEvents.map((event, index) => {
              const alert = event.alert || {};
              return <article className="monitor-live-event" key={alert.id || `${event.timestamp}:${index}`}>
                <span className="live-event-icon"><Radio size={15} /></span>
                <div><div><strong>{alert.title || event.event}</strong><span>{formatTime(alert.created_at || event.timestamp)}</span></div>
                  {alert.endpoint && <EndpointLabel method={alert.metrics?.method || ""} endpoint={alert.endpoint} />}
                  <p>{alert.message || "Monitoring heartbeat received."}</p>
                  {alert.severity && <span className={`severity-badge severity-${alert.severity.toLowerCase()}`}>{alert.severity}</span>}
                </div>
              </article>;
            })}
            {!liveEvents.length && <div className="stage-state"><Radio size={20} /><span>Waiting for project alerts. A heartbeat confirms the connection is still open.</span></div>}
          </div>
        </section>
      )}

      {projectId && !loading && section === "alerts" && (
        <section className="stage-panel monitor-table-panel">
          <div className="stage-toolbar"><div><strong>Persistent alerts</strong><span>{unreadCount} unread · acknowledge or resolve alerts as work progresses.</span></div></div>
          <div className="monitor-alert-list">
            {alerts.map((alert) => <article className={`monitor-alert ${alert.read_at ? "" : "is-unread"}`} key={alert.id}>
              <span className={`monitor-alert-icon severity-${alert.severity.toLowerCase()}`}><AlertTriangle size={16} /></span>
              <div className="monitor-alert-main">
                <div className="monitor-alert-heading"><strong>{alert.title}</strong><span className={`monitor-state ${alert.status === "OPEN" ? "is-running" : ""}`}>{alert.status}</span><small>{formatTime(alert.created_at)}</small></div>
                {alert.endpoint && <EndpointLabel method="" endpoint={alert.endpoint} />}
                <p>{alert.message}</p><small>{alert.recommendation}</small>
              </div>
              <div className="monitor-row-actions">
                {!alert.read_at && <Button variant="ghost" size="sm" onClick={() => updateAlert(alert, "read")}>Mark read</Button>}
                {alert.status === "OPEN" && <Button variant="outline" size="sm" onClick={() => updateAlert(alert, "acknowledge")}>Acknowledge</Button>}
                {alert.status !== "RESOLVED" && <Button variant="outline" size="sm" onClick={() => updateAlert(alert, "resolve")}>Resolve</Button>}
              </div>
            </article>)}
            {!alerts.length && <div className="stage-state"><CircleAlert size={20} /><span>No monitoring alerts have been recorded.</span></div>}
          </div>
        </section>
      )}

      {section === "live" && !projectId && <div className="stage-empty"><Radio size={22} /><strong>Select a project</strong><span>Live alerts are scoped to one authorized project.</span></div>}
    </div>
  );
}
