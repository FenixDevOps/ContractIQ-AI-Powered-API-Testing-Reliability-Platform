import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Braces, ChevronLeft, ChevronRight, Download, FileUp, GitCompareArrows, Printer, RefreshCw, Search, ShieldAlert, Trash2 } from "lucide-react";
import { Button } from "../components/ui/button.jsx";
import {
  compareSpecifications,
  deleteCompatibilityComparison,
  downloadCompatibilityJSON,
  getCompatibilityChanges,
  getCompatibilityHistory,
  getCompatibilitySummary,
  getProjectSpecifications,
  getProjects,
  getSpecificationEndpoints,
  importSpecification,
} from "../services/api.js";

export function ProjectsPage({ onImport, onOpenExplorer }) {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try { setProjects(await getProjects()); }
    catch (caught) { setError(caught.message); }
    finally { setLoading(false); }
  }

  async function changeHistoryPage(page) {
    try {
      setLoading(true);
      setHistory(await getCompatibilityHistory(projectId, page, 20));
      setHistoryPage(page);
    } catch (caught) { setError(caught.message); }
    finally { setLoading(false); }
  }

  useEffect(() => { void load(); }, []);

  return (
    <div className="placeholder-page">
      <div className="page-heading-row">
        <div><div className="page-breadcrumb"><span>Workspace</span><ChevronRight size={13} /><strong>Projects</strong></div><h1>Projects</h1><p className="page-description">Manage API contracts and their imported versions.</p></div>
        <Button className="import-button" onClick={onImport}><FileUp size={15} /> Import API specification</Button>
      </div>
      <section className="stage-panel">
        <div className="stage-toolbar"><div><strong>All projects</strong><span>{projects.length} projects in this workspace</span></div><Button variant="ghost" size="sm" onClick={load}><RefreshCw size={13} /> Refresh</Button></div>
        {loading ? <div className="stage-state">Loading projects...</div> : error ? <div className="stage-error">{error}</div> : projects.length === 0 ? (
          <div className="stage-empty"><Braces size={22} /><strong>No API projects yet</strong><span>Import an OpenAPI specification to create your first project.</span><Button variant="secondary" size="sm" onClick={onImport}>Import specification <ArrowRight size={14} /></Button></div>
        ) : (
          <div className="table-scroll"><table className="data-table stage-table"><thead><tr><th>PROJECT</th><th>SPECIFICATIONS</th><th>LATEST VERSION</th><th>ENDPOINTS</th><th>UPDATED</th></tr></thead><tbody>
            {projects.map((project) => <tr key={project.id} onClick={() => onOpenExplorer(project.id)}><td><strong>{project.name}</strong><small>{project.description || "No description"}</small></td><td>{project.specification_count}</td><td>{project.latest_version ? `v${project.latest_version}` : "-"}</td><td>{project.endpoint_count}</td><td>{new Date(project.updated_at).toLocaleString()}</td></tr>)}
          </tbody></table></div>
        )}
      </section>
    </div>
  );
}

export function ExplorerPage({ onImport, initialProjectId = "" }) {
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(initialProjectId);
  const [specifications, setSpecifications] = useState([]);
  const [selectedSpecification, setSelectedSpecification] = useState("");
  const [endpoints, setEndpoints] = useState([]);
  const [query, setQuery] = useState("");
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (initialProjectId) setSelectedProject(initialProjectId);
  }, [initialProjectId]);

  async function loadProjects() {
    try {
      const result = await getProjects();
      setProjects(result);
      if (result.length && !selectedProject) setSelectedProject(result[0].id);
    } catch (caught) { setError(caught.message); }
  }
  useEffect(() => { void loadProjects(); }, []);
  useEffect(() => {
    if (!selectedProject) return;
    void getProjectSpecifications(selectedProject).then((items) => {
      setSpecifications(items);
      setSelectedSpecification(items[0]?.id || "");
      setError("");
    }).catch((caught) => setError(caught.message));
  }, [selectedProject]);
  useEffect(() => {
    if (!selectedSpecification) { setEndpoints([]); return; }
    void getSpecificationEndpoints(selectedSpecification).then((items) => { setEndpoints(items); setDetail(items[0] || null); }).catch((caught) => setError(caught.message));
  }, [selectedSpecification]);

  const filtered = useMemo(
    () => endpoints.filter((endpoint) =>
      `${endpoint.method} ${endpoint.path} ${endpoint.summary || ""} ${endpoint.tags.join(" ")}`.toLowerCase().includes(query.toLowerCase())
    ),
    [endpoints, query]
  );

  return (
    <div className="placeholder-page">
      <div className="page-heading-row"><div><div className="page-breadcrumb"><span>Workspace</span><ChevronRight size={13} /><strong>API Explorer</strong></div><h1>API Explorer</h1><p className="page-description">Search operations and inspect parsed contract details.</p></div><Button className="import-button" onClick={onImport}><FileUp size={15} /> Import API specification</Button></div>
      {error && <div className="stage-error">{error}</div>}
      <div className="explorer-controls">
        <label>Project<select value={selectedProject} onChange={(event) => setSelectedProject(event.target.value)}><option value="">Select project</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label>
        <label>Specification<select value={selectedSpecification} onChange={(event) => setSelectedSpecification(event.target.value)}><option value="">Select specification</option>{specifications.map((item) => <option key={item.id} value={item.id}>v{item.version_number} · {item.title}</option>)}</select></label>
        <label className="explorer-search"><Search size={14} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search endpoints" /></label>
      </div>
      {endpoints.length === 0 ? <div className="stage-empty explorer-empty"><Braces size={22} /><strong>No endpoints to display</strong><span>Import a specification with paths and HTTP operations.</span></div> : (
        <div className="explorer-layout"><section className="stage-panel endpoint-list"><table className="data-table stage-table"><thead><tr><th>METHOD</th><th>PATH</th><th>SUMMARY</th><th>TAGS</th></tr></thead><tbody>{filtered.map((endpoint) => <tr className={detail?.id === endpoint.id ? "row-selected" : ""} key={endpoint.id} onClick={() => setDetail(endpoint)}><td><span className={`method method-${endpoint.method.toLowerCase()}`}>{endpoint.method}</span></td><td><code>{endpoint.path}</code></td><td>{endpoint.summary || "-"}</td><td>{endpoint.tags.join(", ") || "-"}</td></tr>)}</tbody></table></section>
        {detail && <aside className="stage-panel endpoint-detail"><div className="detail-heading"><span className={`method method-${detail.method.toLowerCase()}`}>{detail.method}</span><code>{detail.path}</code></div>{detail.summary && <h3>{detail.summary}</h3>}{detail.description && <p>{detail.description}</p>}<DetailSection title="Parameters" value={detail.parameters} /><DetailSection title="Request body" value={detail.request_body} /><DetailSection title="Responses" value={detail.responses} /><DetailSection title="Security" value={detail.security} /></aside>}</div>
      )}
    </div>
  );
}

function DetailSection({ title, value }) {
  if (!value || (Array.isArray(value) && value.length === 0) || (typeof value === "object" && Object.keys(value).length === 0)) return null;
  return <section className="detail-section"><h4>{title}</h4><pre>{JSON.stringify(value, null, 2)}</pre></section>;
}

export function ChangesPage() {
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState("");
  const [versions, setVersions] = useState([]);
  const [beforeId, setBeforeId] = useState("");
  const [afterId, setAfterId] = useState("");
  const [history, setHistory] = useState({ items: [], total: 0, summary: {} });
  const [historyPage, setHistoryPage] = useState(1);
  const [report, setReport] = useState(null);
  const [changes, setChanges] = useState([]);
  const [changeTotal, setChangeTotal] = useState(0);
  const [changePage, setChangePage] = useState(1);
  const [filters, setFilters] = useState({ severity: "", category: "", path: "" });
  const [loading, setLoading] = useState(false);
  const [comparing, setComparing] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getProjects().then((items) => {
      setProjects(items);
      if (items[0]) setProjectId(items[0].id);
    }).catch((caught) => setError(caught.message));
  }, []);

  useEffect(() => {
    if (!projectId) {
      setVersions([]);
      setHistory({ items: [], total: 0, summary: {} });
      setHistoryPage(1);
      setReport(null);
      return;
    }
    let active = true;
    setLoading(true);
    setHistory({ items: [], total: 0, summary: {} });
    setHistoryPage(1);
    setReport(null);
    setFilters({ severity: "", category: "", path: "" });
    Promise.all([getProjectSpecifications(projectId), getCompatibilityHistory(projectId, 1, 20)])
      .then(([specs, comparisons]) => {
        if (!active) return;
        setVersions(specs);
        setBeforeId(specs[1]?.id || "");
        setAfterId(specs[0]?.id || "");
        setHistory(comparisons);
        setReport(null);
        setChanges([]);
      })
      .catch((caught) => { if (active) setError(caught.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [projectId]);

  async function loadChanges(comparisonId, nextFilters = filters, page = 1) {
    const result = await getCompatibilityChanges(comparisonId, { ...nextFilters, page, page_size: 100 });
    setChanges(result.items);
    setChangeTotal(result.total);
    setChangePage(page);
  }

  async function openReport(comparisonOrId) {
    setLoading(true);
    setError("");
    try {
      const details = await getCompatibilitySummary(
        typeof comparisonOrId === "string" ? comparisonOrId : comparisonOrId.id
      );
      setReport(details);
      await loadChanges(details.id);
    } catch (caught) { setError(caught.message); }
    finally { setLoading(false); }
  }

  async function runComparison() {
    if (!beforeId || !afterId || beforeId === afterId) return;
    setComparing(true);
    setError("");
    try {
      const comparison = await compareSpecifications(beforeId, afterId);
      await openReport(comparison.id);
      setHistoryPage(1);
      const refreshed = await getCompatibilityHistory(projectId, 1, 20);
      setHistory(refreshed);
    } catch (caught) { setError(caught.message); }
    finally { setComparing(false); }
  }

  async function applyFilter(key, value) {
    const next = { ...filters, [key]: value };
    setFilters(next);
    if (report) {
      try { await loadChanges(report.id, next); }
      catch (caught) { setError(caught.message); }
    }
  }

  async function exportReport() {
    if (!report) return;
    setExporting(true);
    setError("");
    try { await downloadCompatibilityJSON(report.id); }
    catch (caught) { setError(caught.message); }
    finally { setExporting(false); }
  }

  async function removeComparison(comparisonId) {
    try {
      await deleteCompatibilityComparison(comparisonId);
      setHistory(await getCompatibilityHistory(projectId, historyPage, 20));
      if (report?.id === comparisonId) {
        setReport(null);
        setChanges([]);
      }
    } catch (caught) { setError(caught.message); }
  }

  return (
    <div className="placeholder-page compatibility-page">
      <div className="page-heading-row">
        <div><div className="page-breadcrumb"><span>Workspace</span><ChevronRight size={13} /><strong>Breaking Changes</strong></div><h1>Breaking change detection</h1><p className="page-description">Compare imported OpenAPI versions and review deterministic compatibility findings.</p></div>
      </div>
      {error && <div className="stage-error" role="alert">{error}</div>}

      <section className="compatibility-metrics" aria-label="Compatibility overview">
        <Metric label="Comparisons" value={history.summary?.comparisons || 0} />
        <Metric label="Breaking changes" value={history.summary?.breaking_changes || 0} tone="critical" />
        <Metric label="Potential risks" value={history.summary?.potentially_breaking_changes || 0} tone="warning" />
        <Metric label="Non-breaking changes" value={history.summary?.non_breaking_changes || 0} tone="safe" />
        <Metric label="Average score" value={`${history.summary?.average_compatibility_score ?? 0}`} suffix="/ 100" />
      </section>

      <section className="stage-panel compatibility-compare">
        <div className="stage-toolbar"><div><strong>Compare versions</strong><span>Select two different specifications in the same project.</span></div></div>
        <div className="compare-controls">
          <label>Project<select value={projectId} onChange={(event) => setProjectId(event.target.value)}><option value="">Select project</option>{projects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <label>Previous specification<select value={beforeId} onChange={(event) => setBeforeId(event.target.value)}><option value="">Select previous version</option>{versions.map((item) => <option key={item.id} value={item.id}>v{item.version_number} · {item.api_version} · {item.title}</option>)}</select></label>
          <label>New specification<select value={afterId} onChange={(event) => setAfterId(event.target.value)}><option value="">Select new version</option>{versions.map((item) => <option key={item.id} value={item.id}>v{item.version_number} · {item.api_version} · {item.title}</option>)}</select></label>
          <Button onClick={runComparison} disabled={comparing || !beforeId || !afterId || beforeId === afterId}>
            {comparing ? <RefreshCw className="spin-icon" size={14} /> : <GitCompareArrows size={14} />}
            {comparing ? "Comparing..." : "Compare versions"}
          </Button>
        </div>
        {beforeId && beforeId === afterId && <p className="comparison-warning">Choose two different specifications to continue.</p>}
      </section>

      {report && (
        <section className="stage-panel comparison-report">
          <div className="stage-toolbar report-heading">
            <div><strong>Compatibility report</strong><span>{report.comparison_metadata?.api_name} · v{report.comparison_metadata?.old_version_number} → v{report.comparison_metadata?.new_version_number}</span></div>
            <div className="report-actions">
              <span className={`compat-status status-${report.overall_status.toLowerCase().replaceAll("_", "-")}`}>{report.overall_status.replaceAll("_", " ")}</span>
              <Button variant="outline" size="sm" onClick={exportReport} disabled={exporting}><Download size={13} /> {exporting ? "Exporting..." : "JSON report"}</Button>
              <Button variant="outline" size="sm" onClick={() => window.print()}><Printer size={13} /> Print</Button>
            </div>
          </div>
          <div className="report-score-row">
            <div className="compat-score"><strong>{report.compatibility_score}</strong><span>/ 100</span></div>
            <span className="score-disclaimer">{report.comparison_metadata?.score_note}</span>
            <span className="report-count">{report.total_changes} detected changes</span>
          </div>
          <div className="endpoint-summary">
            {Object.entries(report.comparison_metadata?.endpoint_summary || {}).map(([label, value]) => (
              <div key={label}><strong>{value}</strong><span>{label.replaceAll("_", " ")}</span></div>
            ))}
          </div>
          <div className="testing-filters compatibility-filters">
            <label>Severity<select value={filters.severity} onChange={(event) => applyFilter("severity", event.target.value)}><option value="">All severities</option>{["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"].map((item) => <option key={item}>{item}</option>)}</select></label>
            <label>Category<select value={filters.category} onChange={(event) => applyFilter("category", event.target.value)}><option value="">All categories</option>{["ENDPOINT", "PARAMETER", "REQUEST_BODY", "RESPONSE", "RESPONSE_SCHEMA", "SECURITY", "CONTENT_TYPE"].map((item) => <option key={item}>{item}</option>)}</select></label>
            <label className="compat-path-filter">Endpoint<input value={filters.path} onChange={(event) => applyFilter("path", event.target.value)} placeholder="Filter by path" /></label>
            <span className="compat-filter-count">{changeTotal} findings</span>
          </div>
          {loading ? <div className="stage-state">Loading comparison...</div> : changes.length === 0 ? (
            <div className="stage-empty"><ShieldAlert size={20} /><strong>No changes match these filters</strong><span>Try changing a filter, or compare versions with different contracts.</span></div>
          ) : <div className="compatibility-changes">
            {changes.map((change) => <article className="compat-change" key={change.id}>
              <div className="compat-change-heading">
                <span className={`severity-badge severity-${change.severity.toLowerCase()}`}>{change.severity}</span>
                <span className="compat-category">{change.category.replaceAll("_", " ")}</span>
                {change.method && <span className={`method method-${change.method.toLowerCase()}`}>{change.method}</span>}
                {change.path && <code>{change.path}</code>}
                <strong>{change.change_type.replaceAll("_", " ")}</strong>
                <span className={`classification classification-${change.compatibility.toLowerCase().replaceAll("_", "-")}`}>{change.compatibility.replaceAll("_", " ")}</span>
              </div>
              {change.property_name && <div className="compat-property">Property: <code>{change.property_name}</code></div>}
              <p>{change.explanation}</p>
              <div className="compat-values">
                <div><span>Previous</span><pre>{formatValue(change.old_value)}</pre></div>
                <div><span>New</span><pre>{formatValue(change.new_value)}</pre></div>
              </div>
              <div className="compat-recommendation"><strong>Recommended action</strong><span>{change.recommendation}</span></div>
            </article>)}
          </div>}
          {changeTotal > 100 && <div className="compat-pagination">
            <Button variant="outline" size="sm" disabled={changePage <= 1} onClick={() => loadChanges(report.id, filters, changePage - 1)}><ChevronLeft size={13} /> Previous</Button>
            <span>Page {changePage} of {Math.ceil(changeTotal / 100)}</span>
            <Button variant="outline" size="sm" disabled={changePage * 100 >= changeTotal} onClick={() => loadChanges(report.id, filters, changePage + 1)}>Next <ChevronRight size={13} /></Button>
          </div>}
          {report.comparison_metadata?.limitations?.map((limitation) => <p className="limitations" key={limitation}>{limitation}</p>)}
        </section>
      )}

      <section className="stage-panel compatibility-history">
        <div className="stage-toolbar"><div><strong>Comparison history</strong><span>{history.total || 0} saved comparisons</span></div><Button variant="ghost" size="sm" onClick={() => projectId && getCompatibilityHistory(projectId, historyPage, 20).then(setHistory).catch((caught) => setError(caught.message))}><RefreshCw size={13} /> Refresh</Button></div>
        {loading && !report ? <div className="stage-state">Loading comparison history...</div> : history.items?.length ? (
          <div className="table-scroll"><table className="data-table stage-table compatibility-table"><thead><tr><th>VERSIONS</th><th>STATUS</th><th>SCORE</th><th>BREAKING</th><th>DATE</th><th>ACTIONS</th></tr></thead><tbody>
            {history.items.map((item) => <tr key={item.id}>
              <td><strong>v{item.comparison_metadata?.old_version_number} → v{item.comparison_metadata?.new_version_number}</strong><small>{item.comparison_metadata?.api_name}</small></td>
              <td><span className={`compat-status status-${item.overall_status.toLowerCase().replaceAll("_", "-")}`}>{item.overall_status.replaceAll("_", " ")}</span></td>
              <td>{item.compatibility_score}/100</td><td>{item.breaking_changes}</td><td>{new Date(item.created_at).toLocaleString()}</td>
              <td><div className="history-actions"><Button variant="outline" size="sm" onClick={() => openReport(item.id)}>View report</Button><Button variant="ghost" size="icon" aria-label="Delete comparison" onClick={() => removeComparison(item.id)}><Trash2 size={13} /></Button></div></td>
            </tr>)}
          </tbody></table></div>
        ) : <div className="stage-empty"><GitCompareArrows size={20} /><strong>No comparisons saved</strong><span>Compare two versions to create your first compatibility report.</span></div>}
        {history.total > 20 && <div className="compat-pagination">
          <Button variant="outline" size="sm" disabled={historyPage <= 1} onClick={() => changeHistoryPage(historyPage - 1)}><ChevronLeft size={13} /> Previous</Button>
          <span>Page {historyPage} of {Math.ceil(history.total / 20)}</span>
          <Button variant="outline" size="sm" disabled={historyPage * 20 >= history.total} onClick={() => changeHistoryPage(historyPage + 1)}>Next <ChevronRight size={13} /></Button>
        </div>}
      </section>
    </div>
  );
}

function Metric({ label, value, suffix = "", tone = "" }) {
  return <div className={`metric-panel compatibility-metric ${tone}`}><span>{label}</span><strong>{value}{suffix && <small>{suffix}</small>}</strong></div>;
}

function formatValue(value) {
  if (value === null || value === undefined) return "Not present";
  return typeof value === "string" ? value : JSON.stringify(value, null, 2);
}
