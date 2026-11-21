import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Braces, ChevronRight, Download, FileUp, GitCompareArrows, RefreshCw, Search } from "lucide-react";
import { Button } from "../components/ui/button.jsx";
import {
  compareSpecifications,
  getProjectSpecifications,
  getProjects,
  getSpecificationEndpoints,
  getSpecificationVersions,
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
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => { getProjects().then((items) => { setProjects(items); if (items[0]) setProjectId(items[0].id); }).catch((caught) => setError(caught.message)); }, []);
  useEffect(() => {
    if (!projectId) return;
    getProjectSpecifications(projectId).then((items) => { setVersions(items); setBeforeId(items[1]?.id || ""); setAfterId(items[0]?.id || ""); }).catch((caught) => setError(caught.message));
  }, [projectId]);

  async function runComparison() {
    if (!beforeId || !afterId) return;
    try { setReport(await compareSpecifications(beforeId, afterId)); setError(""); } catch (caught) { setError(caught.message); }
  }

  return (
    <div className="placeholder-page"><div className="page-heading-row"><div><div className="page-breadcrumb"><span>Workspace</span><ChevronRight size={13} /><strong>Contract Changes</strong></div><h1>Contract Changes</h1><p className="page-description">Compare imported specification versions structurally.</p></div></div>
      {error && <div className="stage-error">{error}</div>}
      <section className="stage-panel compare-controls"><label>Project<select value={projectId} onChange={(event) => setProjectId(event.target.value)}>{projects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Before<select value={beforeId} onChange={(event) => setBeforeId(event.target.value)}>{versions.map((item) => <option key={item.id} value={item.id}>v{item.version_number} · {item.original_filename}</option>)}</select></label><label>After<select value={afterId} onChange={(event) => setAfterId(event.target.value)}>{versions.map((item) => <option key={item.id} value={item.id}>v{item.version_number} · {item.original_filename}</option>)}</select></label><Button onClick={runComparison} disabled={!beforeId || !afterId}><GitCompareArrows size={14} /> Compare</Button></section>
      {!report ? <div className="stage-empty"><GitCompareArrows size={22} /><strong>No comparison selected</strong><span>Choose two specification versions to see structural changes.</span></div> : (
        <div className="stage-panel comparison-report"><div className="stage-toolbar"><div><strong>Comparison report</strong><span>{report.change_count} changes detected</span></div></div><div className="comparison-list">{report.changes.length === 0 ? <div className="stage-state">No structural changes detected.</div> : report.changes.map((change, index) => <article className={`change-item ${change.potentially_breaking ? "breaking" : ""}`} key={index}><div><strong>{change.key || change.kind}</strong><span>{change.classification}</span></div>{change.modifications && <pre>{JSON.stringify(change.modifications, null, 2)}</pre>}</article>)}</div><p className="limitations">{report.limitations.join(" ")}</p></div>
      )}
    </div>
  );
}
