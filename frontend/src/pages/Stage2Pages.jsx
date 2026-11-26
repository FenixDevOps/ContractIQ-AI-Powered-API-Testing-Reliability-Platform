import { useCallback, useEffect, useMemo, useState } from "react";
import { Archive, ArrowRight, Braces, ChevronLeft, ChevronRight, Crown, Download, FileUp, GitCompareArrows, Pencil, Printer, RefreshCw, Search, ShieldAlert, Trash2, UserPlus, Users, X } from "lucide-react";
import { Button } from "../components/ui/button.jsx";
import {
  compareSpecifications,
  archiveProject,
  createProject,
  deleteProject,
  deleteCompatibilityComparison,
  downloadCompatibilityJSON,
  getCompatibilityChanges,
  getCompatibilityHistory,
  getCompatibilitySummary,
  getProjectSpecifications,
  getProjectActivity,
  getProjectDashboard,
  getProjectInvites,
  getProjectMembers,
  getProjects,
  getSpecificationEndpoints,
  importSpecification,
  inviteProjectMember,
  removeProjectMember,
  restoreProject,
  revokeProjectInvite,
  updateProject,
  updateProjectMemberRole,
  transferProjectOwnership,
} from "../services/api.js";

export function ProjectsPage({ onImport, onOpenExplorer, onProjectsChanged }) {
  const [projects, setProjects] = useState([]);
  const [query, setQuery] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [saving, setSaving] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [editingProject, setEditingProject] = useState(null);
  const [projectForm, setProjectForm] = useState({ name: "", description: "" });
  const [dashboard, setDashboard] = useState(null);
  const [teamProject, setTeamProject] = useState(null);
  const [members, setMembers] = useState([]);
  const [invites, setInvites] = useState([]);
  const [inviteForm, setInviteForm] = useState({ email: "", role: "MEMBER" });

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try { setProjects(await getProjects({ includeArchived })); }
    catch (caught) { setError(caught.message); }
    finally { setLoading(false); }
  }, [includeArchived]);

  useEffect(() => { void load(); }, [load]);

  const filteredProjects = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return projects.filter((project) =>
      `${project.name} ${project.description || ""}`.toLowerCase().includes(normalized)
    );
  }, [projects, query]);

  async function saveProject(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      if (editingProject) {
        await updateProject(editingProject.id, projectForm);
        setNotice("Project details updated.");
      } else {
        await createProject(projectForm);
        setNotice("Project created.");
      }
      setEditingProject(null);
      setShowCreate(false);
      setProjectForm({ name: "", description: "" });
      await load();
      onProjectsChanged?.();
    } catch (caught) {
      setError(caught.message);
    } finally {
      setSaving(false);
    }
  }

  function beginEdit(project) {
    setEditingProject(project);
    setProjectForm({ name: project.name, description: project.description || "" });
    setShowCreate(true);
  }

  async function changeArchiveState(project) {
    setError("");
    setNotice("");
    try {
      if (project.is_archived) {
        await restoreProject(project.id);
        setNotice(`${project.name} restored.`);
      } else {
        if (!window.confirm(`Archive ${project.name}? Its monitoring checks will be paused.`)) return;
        await archiveProject(project.id);
        setNotice(`${project.name} archived.`);
      }
      await load();
      onProjectsChanged?.();
    } catch (caught) {
      setError(caught.message);
    }
  }

  async function removeProject(project) {
    if (!window.confirm(`Permanently delete ${project.name} and its associated API data? This cannot be undone.`)) return;
    setError("");
    setNotice("");
    try {
      await deleteProject(project.id);
      setNotice(`${project.name} deleted.`);
      if (dashboard?.project.id === project.id) setDashboard(null);
      await load();
      onProjectsChanged?.();
    } catch (caught) {
      setError(caught.message);
    }
  }

  async function openDashboard(project) {
    setTeamProject(null);
    setError("");
    try {
      const [details, events] = await Promise.all([
        getProjectDashboard(project.id),
        getProjectActivity(project.id, 1, 10),
      ]);
      setDashboard({ ...details, activity: events });
    } catch (caught) {
      setError(caught.message);
    }
  }

  async function openTeam(project) {
    setDashboard(null);
    setTeamProject(project);
    setError("");
    try {
      const [currentMembers, currentInvites] = await Promise.all([
        getProjectMembers(project.id),
        project.current_user_role === "OWNER" || project.current_user_role === "ADMIN"
          ? getProjectInvites(project.id)
          : Promise.resolve([]),
      ]);
      setMembers(currentMembers);
      setInvites(currentInvites);
    } catch (caught) {
      setError(caught.message);
    }
  }

  async function sendInvite(event) {
    event.preventDefault();
    if (!teamProject) return;
    setSaving(true);
    setError("");
    try {
      await inviteProjectMember(teamProject.id, inviteForm.email, inviteForm.role);
      setInviteForm({ email: "", role: "MEMBER" });
      setNotice("Invitation sent by email.");
      await openTeam(teamProject);
    } catch (caught) {
      setError(caught.message);
    } finally {
      setSaving(false);
    }
  }

  async function changeRole(member, role) {
    try {
      await updateProjectMemberRole(teamProject.id, member.user_id, role);
      setMembers((current) => current.map((item) => item.user_id === member.user_id ? { ...item, role } : item));
      setNotice(`${member.full_name} is now ${role.toLowerCase()}.`);
    } catch (caught) {
      setError(caught.message);
    }
  }

  async function removeMember(member) {
    if (!window.confirm(`Remove ${member.full_name} from ${teamProject.name}?`)) return;
    try {
      await removeProjectMember(teamProject.id, member.user_id);
      setMembers((current) => current.filter((item) => item.user_id !== member.user_id));
      setNotice(`${member.full_name} removed from the project.`);
    } catch (caught) {
      setError(caught.message);
    }
  }

  async function transferOwnership(member) {
    if (!window.confirm(`Transfer ownership of ${teamProject.name} to ${member.full_name}? Your role will become admin.`)) return;
    try {
      await transferProjectOwnership(teamProject.id, member.user_id);
      setTeamProject(null);
      setNotice(`Project ownership transferred to ${member.full_name}.`);
      await load();
      onProjectsChanged?.();
    } catch (caught) {
      setError(caught.message);
    }
  }

  async function revokeInvite(invite) {
    try {
      await revokeProjectInvite(teamProject.id, invite.id);
      setInvites((current) => current.filter((item) => item.id !== invite.id));
      setNotice(`Invitation for ${invite.email} revoked.`);
    } catch (caught) {
      setError(caught.message);
    }
  }

  const canEdit = teamProject
    ? ["OWNER", "ADMIN", "MEMBER"].includes(teamProject.current_user_role)
    : false;
  const canManageTeam = teamProject
    ? ["OWNER", "ADMIN"].includes(teamProject.current_user_role)
    : false;

  return (
    <div className="placeholder-page projects-page">
      <div className="page-heading-row">
        <div><div className="page-breadcrumb"><span>Workspace</span><ChevronRight size={13} /><strong>Projects</strong></div><h1>Projects</h1><p className="page-description">Manage API contracts, project access, and activity.</p></div>
        <div className="project-page-actions">
          <Button variant="outline" onClick={onImport}><FileUp size={15} /> Import specification</Button>
          <Button className="import-button" onClick={() => { setEditingProject(null); setProjectForm({ name: "", description: "" }); setShowCreate(true); }}>Create project</Button>
        </div>
      </div>
      {error && <div className="stage-error" role="alert">{error}</div>}
      {notice && <div className="workspace-notice" role="status">{notice}</div>}
      {showCreate && (
        <section className="stage-panel project-edit-panel">
          <div className="stage-toolbar"><div><strong>{editingProject ? "Edit project" : "Create project"}</strong><span>Project data is available only to its members.</span></div><Button variant="ghost" size="icon" aria-label="Close form" onClick={() => setShowCreate(false)}><X size={15} /></Button></div>
          <form className="project-form" onSubmit={saveProject}>
            <label>Project name<input required minLength={1} maxLength={255} value={projectForm.name} onChange={(event) => setProjectForm({ ...projectForm, name: event.target.value })} /></label>
            <label>Description<textarea maxLength={4000} value={projectForm.description} onChange={(event) => setProjectForm({ ...projectForm, description: event.target.value })} rows={3} /></label>
            <div className="project-form-actions"><Button type="submit" disabled={saving}>{saving ? "Saving…" : editingProject ? "Save changes" : "Create project"}</Button><Button type="button" variant="ghost" onClick={() => setShowCreate(false)}>Cancel</Button></div>
          </form>
        </section>
      )}
      <section className="stage-panel">
        <div className="stage-toolbar projects-toolbar">
          <div><strong>Your projects</strong><span>{filteredProjects.length} of {projects.length} projects</span></div>
          <div className="projects-toolbar-actions"><label className="projects-search"><Search size={14} /><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search projects" /></label><label className="archived-filter"><input type="checkbox" checked={includeArchived} onChange={(event) => setIncludeArchived(event.target.checked)} /> Include archived</label><Button variant="ghost" size="sm" onClick={() => void load()}><RefreshCw size={13} /> Refresh</Button></div>
        </div>
        {loading ? <div className="stage-state">Loading projects...</div> : error ? <div className="stage-error">{error}</div> : projects.length === 0 ? (
          <div className="stage-empty"><Braces size={22} /><strong>No projects yet</strong><span>Create a project to organize specifications, testing, and monitoring.</span><Button variant="secondary" size="sm" onClick={() => setShowCreate(true)}>Create a project <ArrowRight size={14} /></Button></div>
        ) : filteredProjects.length === 0 ? (
          <div className="stage-empty"><Search size={20} /><strong>No matching projects</strong><span>Adjust the search text or archived filter.</span></div>
        ) : (
          <div className="table-scroll"><table className="data-table stage-table project-table"><thead><tr><th>PROJECT</th><th>SPECS</th><th>ENDPOINTS</th><th>ROLE</th><th>UPDATED</th><th>ACTIONS</th></tr></thead><tbody>
            {filteredProjects.map((project) => <tr key={project.id}>
              <td><strong>{project.name}</strong><small>{project.description || "No description"}</small>{project.is_archived && <span className="project-archived-badge">Archived</span>}</td>
              <td>{project.specification_count}</td><td>{project.endpoint_count}</td><td><span className="role-badge">{project.current_user_role}</span></td><td>{new Date(project.updated_at).toLocaleDateString()}</td>
              <td><div className="project-row-actions"><Button variant="ghost" size="sm" onClick={() => void openDashboard(project)}>Overview</Button><Button variant="ghost" size="icon" aria-label={`Open ${project.name} team`} onClick={() => void openTeam(project)}><Users size={14} /></Button><Button variant="ghost" size="icon" aria-label={`Edit ${project.name}`} disabled={!["OWNER", "ADMIN", "MEMBER"].includes(project.current_user_role) || project.is_archived} onClick={() => beginEdit(project)}><Pencil size={14} /></Button><Button variant="ghost" size="icon" aria-label={`Explore ${project.name} API`} disabled={project.is_archived} onClick={() => onOpenExplorer(project.id)}><Braces size={14} /></Button><Button variant="ghost" size="icon" aria-label={`${project.is_archived ? "Restore" : "Archive"} ${project.name}`} disabled={!["OWNER", "ADMIN"].includes(project.current_user_role)} onClick={() => void changeArchiveState(project)}>{project.is_archived ? <RefreshCw size={14} /> : <Archive size={14} />}</Button>{project.current_user_role === "OWNER" && <Button variant="ghost" size="icon" aria-label={`Delete ${project.name}`} onClick={() => void removeProject(project)}><Trash2 size={14} /></Button>}</div></td>
            </tr>)}
          </tbody></table></div>
        )}
      </section>
      {dashboard && (
        <section className="stage-panel project-dashboard">
          <div className="stage-toolbar"><div><strong>{dashboard.project.name}</strong><span>Project dashboard · actual persisted activity</span></div><div className="project-detail-actions"><Button variant="outline" size="sm" onClick={() => onOpenExplorer(dashboard.project.id)}>Explore API</Button><Button variant="ghost" size="icon" aria-label="Close project dashboard" onClick={() => setDashboard(null)}><X size={14} /></Button></div></div>
          <div className="project-dashboard-metrics">
            <Metric label="Specifications" value={dashboard.specification_count} />
            <Metric label="Endpoints" value={dashboard.endpoint_count} />
            <Metric label="Test runs" value={dashboard.test_run_count} />
            <Metric label="Breaking changes" value={dashboard.breaking_changes_detected} tone="critical" />
            <Metric label="Enabled monitors" value={dashboard.enabled_monitoring_configurations} />
            <Metric label="Active alerts" value={dashboard.active_alert_count} tone="warning" />
          </div>
          <div className="project-dashboard-columns">
            <section><h3>Recent test runs</h3>{dashboard.latest_test_runs.length ? <ul>{dashboard.latest_test_runs.map((run) => <li key={run.id}><span className={`run-status run-status-${run.status.toLowerCase()}`}>{run.status}</span><span>{run.passed_tests} passed · {run.failed_tests} failed</span><time>{new Date(run.started_at).toLocaleString()}</time></li>)}</ul> : <p>No test runs recorded.</p>}</section>
            <section><h3>Recent project activity</h3>{dashboard.activity.length ? <ul>{dashboard.activity.map((item) => <li key={item.id}><span>{item.actor_name || "System"} · {item.action.replaceAll("_", " ")}</span><time>{new Date(item.created_at).toLocaleString()}</time></li>)}</ul> : <p>No project activity recorded.</p>}</section>
          </div>
        </section>
      )}
      {teamProject && (
        <section className="stage-panel project-team-panel">
          <div className="stage-toolbar"><div><strong>Team · {teamProject.name}</strong><span>Project role: {teamProject.current_user_role}</span></div><Button variant="ghost" size="icon" aria-label="Close team" onClick={() => setTeamProject(null)}><X size={14} /></Button></div>
          {canManageTeam && <form className="project-invite-form" onSubmit={sendInvite}><label>Email<input type="email" required maxLength={320} value={inviteForm.email} onChange={(event) => setInviteForm({ ...inviteForm, email: event.target.value })} placeholder="teammate@company.com" /></label><label>Role<select value={inviteForm.role} onChange={(event) => setInviteForm({ ...inviteForm, role: event.target.value })}><option value="MEMBER">Member</option><option value="VIEWER">Viewer</option>{teamProject.current_user_role === "OWNER" && <option value="ADMIN">Admin</option>}</select></label><Button type="submit" disabled={saving}><UserPlus size={14} /> {saving ? "Sending…" : "Invite member"}</Button></form>}
          <div className="table-scroll"><table className="data-table stage-table team-table"><thead><tr><th>MEMBER</th><th>ROLE</th><th>JOINED</th><th>ACTIONS</th></tr></thead><tbody>{members.map((member) => <tr key={member.user_id}><td><strong>{member.full_name}</strong><small>{member.email}</small></td><td>{member.role}</td><td>{new Date(member.joined_at).toLocaleDateString()}</td><td>{canManageTeam && member.role !== "OWNER" && <div className="project-row-actions"><select aria-label={`Role for ${member.full_name}`} value={member.role} onChange={(event) => void changeRole(member, event.target.value)}><option value="MEMBER">Member</option><option value="VIEWER">Viewer</option>{teamProject.current_user_role === "OWNER" && <option value="ADMIN">Admin</option>}</select>{teamProject.current_user_role === "OWNER" && <Button variant="ghost" size="icon" aria-label={`Transfer ownership to ${member.full_name}`} onClick={() => void transferOwnership(member)}><Crown size={14} /></Button>}<Button variant="ghost" size="icon" aria-label={`Remove ${member.full_name}`} onClick={() => void removeMember(member)}><Trash2 size={14} /></Button></div>}</td></tr>)}</tbody></table></div>
          {canManageTeam && <div className="pending-invites"><h3>Pending invitations</h3>{invites.length ? invites.map((invite) => <div key={invite.id}><span>{invite.email} · {invite.role} · expires {new Date(invite.expires_at).toLocaleDateString()}</span><Button variant="ghost" size="sm" onClick={() => void revokeInvite(invite)}>Revoke</Button></div>) : <p>No pending invitations.</p>}</div>}
          {!canEdit && <p className="project-readonly-note">Viewers have read-only access to this project.</p>}
        </section>
      )}
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
