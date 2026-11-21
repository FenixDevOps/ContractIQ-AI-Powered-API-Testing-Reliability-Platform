import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, ChevronRight, Clock3, Play, RefreshCw, Search, WandSparkles } from "lucide-react";
import { Button } from "../components/ui/button.jsx";
import {
  executeAllTests,
  generateTestCases,
  getProjects,
  getProjectSpecifications,
  getTestCases,
  getTestResults,
  getTestRuns,
  getTestingSummary,
  updateTestCase,
} from "../services/api.js";

const initialConfig = {
  base_url: "",
  environment_name: "testing",
  timeout_seconds: 10,
  include_negative_tests: false,
  allow_write_operations: false,
  confirm_destructive: false,
  default_headers: {},
};

export default function TestingPage() {
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState("");
  const [specifications, setSpecifications] = useState([]);
  const [specificationId, setSpecificationId] = useState("");
  const [cases, setCases] = useState([]);
  const [runs, setRuns] = useState([]);
  const [summary, setSummary] = useState(null);
  const [results, setResults] = useState([]);
  const [selectedCase, setSelectedCase] = useState(null);
  const [selectedResult, setSelectedResult] = useState(null);
  const [config, setConfig] = useState(initialConfig);
  const [headersText, setHeadersText] = useState("");
  const [methodFilter, setMethodFilter] = useState("ALL");
  const [categoryFilter, setCategoryFilter] = useState("ALL");
  const [query, setQuery] = useState("");
  const [resultQuery, setResultQuery] = useState("");
  const [resultStatusFilter, setResultStatusFilter] = useState("ALL");
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    getProjects().then((items) => {
      setProjects(items);
      if (items[0]) setProjectId(items[0].id);
    }).catch((caught) => setError(caught.message));
  }, []);

  useEffect(() => {
    if (!projectId) { setSpecifications([]); setSpecificationId(""); return; }
    getProjectSpecifications(projectId).then((items) => {
      setSpecifications(items);
      setSpecificationId(items[0]?.id || "");
    }).catch((caught) => setError(caught.message));
  }, [projectId]);

  async function loadData(id = specificationId) {
    if (!id) return;
    setLoading(true);
    setError("");
    try {
      const [nextCases, nextRuns, nextSummary] = await Promise.all([getTestCases(id), getTestRuns(id), getTestingSummary(id)]);
      setCases(nextCases);
      setRuns(nextRuns);
      setSummary(nextSummary);
      if (nextRuns[0]) setResults(await getTestResults(nextRuns[0].id));
      else setResults([]);
    } catch (caught) { setError(caught.message); }
    finally { setLoading(false); }
  }

  useEffect(() => { if (specificationId) void loadData(specificationId); }, [specificationId]);

  async function generate() {
    if (!specificationId) return;
    setLoading(true);
    setError("");
    setNotice("");
    try {
      const response = await generateTestCases(specificationId);
      setNotice(`${response.created_count} new test cases generated; ${response.total_count} available.`);
      await loadData(specificationId);
    } catch (caught) { setError(caught.message); }
    finally { setLoading(false); }
  }

  async function toggleCase(testCase) {
    try {
      await updateTestCase(testCase.id, { is_enabled: !testCase.is_enabled });
      setCases((items) => items.map((item) => item.id === testCase.id ? { ...item, is_enabled: !item.is_enabled } : item));
    } catch (caught) { setError(caught.message); }
  }

  async function runTests() {
    if (!specificationId || running) return;
    setRunning(true);
    setError("");
    setNotice("");
    try {
      const defaultHeaders = headersText.trim() ? JSON.parse(headersText) : {};
      if (!defaultHeaders || Array.isArray(defaultHeaders) || typeof defaultHeaders !== "object") {
        throw new Error("Default headers must be a JSON object.");
      }
      const run = await executeAllTests(specificationId, { ...config, default_headers: defaultHeaders });
      setNotice(`Run completed: ${run.passed_tests} passed, ${run.failed_tests} failed, ${run.skipped_tests} skipped, ${run.error_tests} errors.`);
      await loadData(specificationId);
    } catch (caught) { setError(caught.message); }
    finally { setRunning(false); }
  }

  async function openRun(run) {
    try {
      setResults(await getTestResults(run.id));
      setSelectedResult(null);
    } catch (caught) { setError(caught.message); }
  }

  const filteredCases = useMemo(() => cases.filter((item) =>
    (methodFilter === "ALL" || item.http_method === methodFilter)
    && (categoryFilter === "ALL" || item.category === categoryFilter)
    && `${item.name} ${item.endpoint_path} ${item.description}`.toLowerCase().includes(query.toLowerCase())
  ), [cases, methodFilter, categoryFilter, query]);
  const filteredResults = useMemo(() => results.filter((item) =>
    (resultStatusFilter === "ALL" || item.status === resultStatusFilter)
    && `${item.test_case_snapshot.name} ${item.test_case_snapshot.endpoint_path} ${item.status}`.toLowerCase().includes(resultQuery.toLowerCase())
  ), [results, resultStatusFilter, resultQuery]);
  const passRate = summary?.success_rate ?? null;
  const latency = summary?.average_response_time_ms == null ? null : Math.round(summary.average_response_time_ms);

  return (
    <div className="placeholder-page testing-page">
      <div className="page-heading-row"><div><div className="page-breadcrumb"><span>Workspace</span><ChevronRight size={13} /><strong>Test Runs</strong></div><h1>Automated API testing</h1><p className="page-description">Generate contract-driven cases, run them against an explicitly approved target, and review real results.</p></div><Button variant="ghost" size="sm" onClick={() => void loadData()}><RefreshCw size={13} /> Refresh</Button></div>
      {error && <div className="stage-error" role="alert">{error}</div>}
      {notice && <div className="testing-notice">{notice}</div>}

      <section className="testing-selectors stage-panel">
        <label>Project<select value={projectId} onChange={(event) => setProjectId(event.target.value)}><option value="">Select project</option>{projects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>Specification<select value={specificationId} onChange={(event) => setSpecificationId(event.target.value)}><option value="">Select specification</option>{specifications.map((item) => <option key={item.id} value={item.id}>v{item.version_number} · {item.title}</option>)}</select></label>
        <span className="testing-selector-hint">{cases.length} test cases · {runs.length} saved runs</span>
      </section>

      <section className="testing-metrics">
        <Metric title="Test cases" value={cases.length} icon={<WandSparkles size={15} />} />
        <Metric title="Test runs" value={runs.length} icon={<Play size={15} />} />
        <Metric title="Passed / failed" value={`${summary?.passed_tests || 0} / ${summary?.failed_tests || 0}`} icon={<CheckCircle2 size={15} />} />
        <Metric title="Pass rate" value={passRate == null ? "—" : `${passRate}%`} icon={<CheckCircle2 size={15} />} />
        <Metric title="Avg. response" value={latency == null ? "—" : `${latency} ms`} icon={<Clock3 size={15} />} />
      </section>
      {summary?.recent_failures?.length > 0 && <section className="stage-panel recent-failures-panel"><div className="stage-toolbar"><div><strong>Recent failures</strong><span>Actual persisted failures and execution errors across runs.</span></div></div><div className="table-scroll"><table className="data-table stage-table"><thead><tr><th>TEST</th><th>ENDPOINT</th><th>STATUS</th><th>ERROR</th></tr></thead><tbody>{summary.recent_failures.map((item) => <tr key={item.id} onClick={() => setSelectedResult(item)}><td>{item.test_case_snapshot.name}</td><td><code>{item.test_case_snapshot.http_method} {item.test_case_snapshot.endpoint_path}</code></td><td><Status status={item.status} /></td><td>{item.error_message || item.validation_errors?.[0]?.message || "Validation failed"}</td></tr>)}</tbody></table></div></section>}

      <section className="stage-panel">
        <div className="stage-toolbar"><div><strong>Generated test cases</strong><span>Generation is deterministic; repeated requests do not create duplicates.</span></div><Button onClick={generate} disabled={!specificationId || loading}><WandSparkles size={14} /> {loading ? "Working..." : "Generate test cases"}</Button></div>
        <div className="testing-filters">
          <label className="testing-search"><Search size={14} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search test cases" /></label>
          <select value={methodFilter} onChange={(event) => setMethodFilter(event.target.value)}><option value="ALL">All methods</option>{["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"].map((item) => <option key={item}>{item}</option>)}</select>
          <select value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)}><option value="ALL">All categories</option>{["STATUS_CODE", "RESPONSE_SCHEMA", "REQUIRED_PARAMETER", "REQUEST_BODY", "CONTENT_TYPE", "NEGATIVE_TEST"].map((item) => <option key={item}>{item}</option>)}</select>
        </div>
        {filteredCases.length === 0 ? <div className="stage-empty"><WandSparkles size={22} /><strong>{cases.length ? "No cases match these filters" : "No generated test cases"}</strong><span>Select a specification and generate cases from its documented operations.</span></div> : (
          <div className="table-scroll"><table className="data-table stage-table testing-table"><thead><tr><th>TEST CASE</th><th>METHOD</th><th>ENDPOINT</th><th>CATEGORY</th><th>EXPECTED</th><th>ENABLED</th></tr></thead><tbody>{filteredCases.map((item) => <tr key={item.id}><td><button type="button" className="case-name" onClick={() => setSelectedCase(item)}>{item.name}</button><small>{item.description}</small></td><td><span className={`method method-${item.http_method.toLowerCase()}`}>{item.http_method}</span></td><td><code>{item.endpoint_path}</code></td><td>{item.category.replaceAll("_", " ")}</td><td>{item.expected_status_codes.join(", ") || "—"}</td><td><input aria-label={`Enable ${item.name}`} type="checkbox" checked={item.is_enabled} onChange={() => toggleCase(item)} /></td></tr>)}</tbody></table></div>
        )}
      </section>

      <section className="stage-panel test-config-panel">
        <div className="stage-toolbar"><div><strong>Execution target</strong><span>Only exact hosts in the backend allowlist can be tested. Redirects are not followed.</span></div></div>
        <div className="test-config-grid">
          <label>Environment<select value={config.environment_name} onChange={(event) => setConfig({ ...config, environment_name: event.target.value, allow_write_operations: event.target.value === "production" ? false : config.allow_write_operations, confirm_destructive: false })}><option>development</option><option>testing</option><option>staging</option><option>production</option></select></label>
          <label className="target-url-field">Target base URL<input type="url" placeholder="https://api.your-domain.example" value={config.base_url} onChange={(event) => setConfig({ ...config, base_url: event.target.value })} /></label>
          <label>Timeout (seconds)<input type="number" min="1" max="30" value={config.timeout_seconds} onChange={(event) => setConfig({ ...config, timeout_seconds: Number(event.target.value) })} /></label>
        </div>
        <label className="headers-config">Default headers (JSON, optional)<textarea value={headersText} onChange={(event) => setHeadersText(event.target.value)} placeholder={'{"Authorization":"Bearer your-token"}'} /></label>
        <div className="test-config-options">
          <label><input type="checkbox" checked={config.include_negative_tests} onChange={(event) => setConfig({ ...config, include_negative_tests: event.target.checked })} /> Include safe negative tests (GET/HEAD/OPTIONS only)</label>
          <label><input type="checkbox" checked={config.allow_write_operations} disabled={config.environment_name === "production"} onChange={(event) => setConfig({ ...config, allow_write_operations: event.target.checked, confirm_destructive: false })} /> Allow POST/PUT/PATCH/DELETE tests{config.environment_name === "production" ? " (disabled in production)" : ""}</label>
        </div>
        {config.environment_name === "production" && <div className="production-safe-note">Production safe mode: only GET, HEAD, and OPTIONS requests can execute.</div>}
        {config.allow_write_operations && <label className="destructive-confirm"><AlertTriangle size={15} /><input type="checkbox" checked={config.confirm_destructive} onChange={(event) => setConfig({ ...config, confirm_destructive: event.target.checked })} /> I explicitly confirm write operations may change data on the selected target.</label>}
        <div className="test-run-action"><span>Requests run sequentially · max 100 cases · {1} MB response limit</span><Button onClick={runTests} disabled={!specificationId || !config.base_url || running || loading}><Play size={14} />{running ? "Running tests..." : "Run enabled tests"}</Button></div>
      </section>

      <section className="stage-panel test-results-panel">
        <div className="stage-toolbar"><div><strong>Test results</strong><span>Click a previous run to inspect its saved report.</span></div><select aria-label="Previous test runs" onChange={(event) => { const run = runs.find((item) => item.id === event.target.value); if (run) void openRun(run); }}><option value="">Latest run</option>{runs.map((run) => <option key={run.id} value={run.id}>{run.environment_name} · {new Date(run.started_at).toLocaleString()}</option>)}</select></div>
        <div className="testing-filters"><label className="testing-search"><Search size={14} /><input value={resultQuery} onChange={(event) => setResultQuery(event.target.value)} placeholder="Search results" /></label><select value={resultStatusFilter} onChange={(event) => setResultStatusFilter(event.target.value)}><option value="ALL">All results</option>{["PASSED", "FAILED", "SKIPPED", "ERROR"].map((item) => <option key={item}>{item}</option>)}</select></div>
        {results.length === 0 ? <div className="stage-empty"><Play size={21} /><strong>No test results yet</strong><span>Run generated test cases to see actual response validation results.</span></div> : (
          filteredResults.length === 0 ? <div className="stage-state">No results match these filters.</div> : <div className="table-scroll"><table className="data-table stage-table testing-table"><thead><tr><th>TEST</th><th>METHOD</th><th>ENDPOINT</th><th>EXPECTED</th><th>ACTUAL</th><th>TIME</th><th>RESULT</th></tr></thead><tbody>{filteredResults.map((item) => <tr key={item.id} onClick={() => setSelectedResult(item)}><td><strong>{item.test_case_snapshot.name}</strong><small>{item.test_case_snapshot.category}</small></td><td>{item.test_case_snapshot.http_method}</td><td><code>{item.test_case_snapshot.endpoint_path}</code></td><td>{item.expected_status_codes.join(", ") || "—"}</td><td>{item.actual_status_code ?? "—"}</td><td>{item.response_time_ms == null ? "—" : `${item.response_time_ms.toFixed(0)} ms`}</td><td><Status status={item.status} /></td></tr>)}</tbody></table></div>
        )}
      </section>

      {selectedCase && <CaseDetails testCase={selectedCase} onClose={() => setSelectedCase(null)} />}
      {selectedResult && <ResultDetails result={selectedResult} onClose={() => setSelectedResult(null)} />}

      <section className="stage-panel run-history-panel"><div className="stage-toolbar"><div><strong>Execution history</strong><span>Previously saved runs remain available when test cases are regenerated.</span></div></div>
        {runs.length === 0 ? <div className="stage-state">No saved test runs.</div> : <div className="table-scroll"><table className="data-table stage-table"><thead><tr><th>RUN</th><th>ENVIRONMENT</th><th>STARTED</th><th>TESTS</th><th>PASS</th><th>FAIL</th><th>DURATION</th><th>STATUS</th></tr></thead><tbody>{runs.map((run) => <tr key={run.id} onClick={() => void openRun(run)}><td><code>{run.id.slice(0, 8)}</code></td><td>{run.environment_name}</td><td>{new Date(run.started_at).toLocaleString()}</td><td>{run.total_tests}</td><td>{run.passed_tests}</td><td>{run.failed_tests}</td><td>{run.duration_ms == null ? "—" : `${run.duration_ms.toFixed(0)} ms`}</td><td><Status status={run.status} /></td></tr>)}</tbody></table></div>}
      </section>
    </div>
  );
}

function Metric({ title, value, icon }) {
  return <article className="metric-panel"><div className="metric-topline"><span>{title}</span>{icon}</div><div className="metric-value">{value}</div><p>Actual persisted data</p></article>;
}

function Status({ status }) {
  return <span className={`run-status run-status-${status.toLowerCase()}`}>{status}</span>;
}

function ResultDetails({ result, onClose }) {
  return (
    <div className="dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="command-dialog result-detail-dialog" role="dialog" aria-modal="true" aria-labelledby="result-detail-title">
        <div className="stage-toolbar"><div><strong id="result-detail-title">{result.test_case_snapshot.name}</strong><span>{result.test_case_snapshot.description}</span></div><Button variant="ghost" size="sm" onClick={onClose}>Close</Button></div>
        <div className="result-detail-summary"><Status status={result.status} /><span>Actual status: {result.actual_status_code ?? "—"}</span><span>Response: {result.response_time_ms == null ? "—" : `${result.response_time_ms.toFixed(0)} ms`}</span></div>
        {result.error_message && <div className="stage-error">{result.error_message}</div>}
        {result.validation_errors.length > 0 && <div className="validation-errors"><strong>Validation issues</strong>{result.validation_errors.map((item, index) => <p key={index}>{item.path ? `${item.path}: ` : ""}{item.message}</p>)}</div>}
        <DetailBlock title="Request" value={result.request_details} /><DetailBlock title="Response" value={result.response_details} />
      </section>
    </div>
  );
}

function CaseDetails({ testCase, onClose }) {
  return (
    <div className="dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="command-dialog result-detail-dialog" role="dialog" aria-modal="true" aria-labelledby="case-detail-title">
        <div className="stage-toolbar"><div><strong id="case-detail-title">{testCase.name}</strong><span>{testCase.description}</span></div><Button variant="ghost" size="sm" onClick={onClose}>Close</Button></div>
        <div className="result-detail-summary"><span>{testCase.category}</span><span>{testCase.http_method} {testCase.endpoint_path}</span><span>Expected: {testCase.expected_status_codes.join(", ") || "—"}</span><Status status={testCase.is_enabled ? "ENABLED" : "SKIPPED"} /></div>
        <DetailBlock title="Request configuration" value={testCase.request_configuration} />
        {testCase.expected_response_schema && <DetailBlock title="Expected response schema" value={testCase.expected_response_schema} />}
      </section>
    </div>
  );
}

function DetailBlock({ title, value }) {
  return <details className="result-detail-block" open><summary>{title}</summary><pre>{JSON.stringify(value, null, 2)}</pre></details>;
}
