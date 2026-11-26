const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();

if (!configuredBaseUrl) {
  throw new Error("VITE_API_BASE_URL is not configured. Add it to frontend/.env.");
}

const API_BASE_URL = configuredBaseUrl.replace(/\/$/, "");
const CSRF_COOKIE_NAME = "contractiq_csrf";
export const API_DOCS_URL = `${API_BASE_URL}/docs`;
let accessToken = "";
let refreshPromise = null;

export function getAccessToken() {
  return accessToken;
}

export function setAccessToken(token) {
  accessToken = token || "";
}

export function clearAccessToken() {
  accessToken = "";
}

function readCookie(name) {
  if (typeof document === "undefined") return "";
  const encodedName = `${encodeURIComponent(name)}=`;
  const entry = document.cookie.split("; ").find((cookie) => cookie.startsWith(encodedName));
  return entry ? decodeURIComponent(entry.slice(encodedName.length)) : "";
}

export async function refreshAuthSession() {
  if (refreshPromise) return refreshPromise;
  const csrfToken = readCookie(CSRF_COOKIE_NAME);
  if (!csrfToken) {
    clearAccessToken();
    return null;
  }
  refreshPromise = (async () => {
    let response;
    try {
      response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
        method: "POST",
        credentials: "include",
        headers: { "X-CSRF-Token": csrfToken, Accept: "application/json" },
      });
    } catch {
      throw new Error("Unable to reach the ContractIQ backend.");
    }
    if (!response.ok) {
      clearAccessToken();
      return null;
    }
    const payload = await response.json();
    setAccessToken(payload.access_token);
    return payload;
  })();
  try {
    return await refreshPromise;
  } finally {
    refreshPromise = null;
  }
}

export async function fetchHealth() {
  const response = await fetch(`${API_BASE_URL}/health`, {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Backend returned HTTP ${response.status}`);
  }

  const payload = await response.json();
  if (payload.status !== "healthy") {
    throw new Error("Backend returned an unexpected health status");
  }

  return payload;
}

async function request(path, options = {}, retryAfterRefresh = true) {
  let response;
  const headers = new Headers(options.headers || {});
  if (accessToken && !path.startsWith("/api/v1/auth/")) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers,
      credentials: "include",
    });
  } catch (error) {
    throw new Error("Unable to reach the ContractIQ backend.");
  }
  if (response.status === 401 && accessToken && !path.startsWith("/api/v1/auth/")) {
    if (retryAfterRefresh) {
      const renewed = await refreshAuthSession().catch(() => null);
      if (renewed) return request(path, options, false);
    }
    clearAccessToken();
    if (typeof window !== "undefined") window.dispatchEvent(new Event("contractiq:auth-expired"));
  }
  if (response.status === 204) return null;
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || `Backend returned HTTP ${response.status}`);
  }
  return payload;
}

export function getProjects({ includeArchived = false } = {}) {
  const query = includeArchived ? "?include_archived=true" : "";
  return request(`/api/v1/projects${query}`);
}

export function createAccount(payload) {
  return request("/api/v1/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function requestEmailVerification(email) {
  return request("/api/v1/auth/email-verification/request", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
}

export function confirmEmailVerification(token) {
  return request("/api/v1/auth/email-verification/confirm", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
}

export function login(payload) {
  return request("/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function logout() {
  const csrfToken = readCookie(CSRF_COOKIE_NAME);
  try {
    await request("/api/v1/auth/logout", {
      method: "POST",
      headers: csrfToken ? { "X-CSRF-Token": csrfToken } : {},
    });
  } finally {
    clearAccessToken();
  }
}

export function requestPasswordReset(email) {
  return request("/api/v1/auth/password-reset/request", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
}

export function confirmPasswordReset(token, newPassword) {
  return request("/api/v1/auth/password-reset/confirm", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, new_password: newPassword }),
  });
}

export function getProfile() {
  return request("/api/v1/auth/me");
}

export function updateProfile(payload) {
  return request("/api/v1/auth/me", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function changePassword(payload) {
  return request("/api/v1/auth/change-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      current_password: payload.currentPassword,
      new_password: payload.newPassword,
    }),
  });
}

export function createProject(payload) {
  return request("/api/v1/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function updateProject(projectId, payload) {
  return request(`/api/v1/projects/${projectId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function archiveProject(projectId) {
  return request(`/api/v1/projects/${projectId}/archive`, { method: "POST" });
}

export function restoreProject(projectId) {
  return request(`/api/v1/projects/${projectId}/restore`, { method: "POST" });
}

export function deleteProject(projectId) {
  return request(`/api/v1/projects/${projectId}?confirm=true`, { method: "DELETE" });
}

export function getProjectDashboard(projectId) {
  return request(`/api/v1/projects/${projectId}/dashboard`);
}

export function getProjectMembers(projectId) {
  return request(`/api/v1/projects/${projectId}/members`);
}

export function inviteProjectMember(projectId, email, role) {
  return request(`/api/v1/projects/${projectId}/invites`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, role }),
  });
}

export function getProjectInvites(projectId) {
  return request(`/api/v1/projects/${projectId}/invites`);
}

export function revokeProjectInvite(projectId, inviteId) {
  return request(`/api/v1/projects/${projectId}/invites/${inviteId}`, { method: "DELETE" });
}

export function updateProjectMemberRole(projectId, userId, role) {
  return request(`/api/v1/projects/${projectId}/members/${userId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role }),
  });
}

export function removeProjectMember(projectId, userId) {
  return request(`/api/v1/projects/${projectId}/members/${userId}`, { method: "DELETE" });
}

export function transferProjectOwnership(projectId, userId) {
  const query = new URLSearchParams({ new_owner_id: userId });
  return request(`/api/v1/projects/${projectId}/transfer-ownership?${query}`, { method: "POST" });
}

export function getProjectActivity(projectId, page = 1, pageSize = 30) {
  return request(`/api/v1/projects/${projectId}/activity?${queryString({ page, page_size: pageSize })}`);
}

export function acceptProjectInvite(token) {
  return request("/api/v1/projects/invites/accept", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
}

export function importSpecification(projectId, file, title) {
  const form = new FormData();
  form.append("file", file);
  if (title) form.append("title", title);
  return request(`/api/v1/projects/${projectId}/specifications/import`, {
    method: "POST",
    body: form,
  });
}

export function getProjectSpecifications(projectId) {
  return request(`/api/v1/projects/${projectId}/specifications`);
}

export function getSpecificationDetails(specificationId) {
  return request(`/api/v1/specifications/${specificationId}`);
}

export function getSpecificationEndpoints(specificationId) {
  return request(`/api/v1/specifications/${specificationId}/endpoints`);
}

export function getSpecificationVersions(specificationId) {
  return request(`/api/v1/specifications/${specificationId}/versions`);
}

export function getRawSpecification(specificationId) {
  return request(`/api/v1/specifications/${specificationId}/raw`);
}

export function compareSpecifications(specificationId, otherSpecificationId) {
  return request("/api/v1/compatibility/compare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      old_specification_id: specificationId,
      new_specification_id: otherSpecificationId,
    }),
  });
}

export function getCompatibilityHistory(projectId, page = 1, pageSize = 20) {
  const query = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  return request(`/api/v1/projects/${projectId}/compatibility?${query}`);
}

export function getCompatibilityDetails(comparisonId) {
  return request(`/api/v1/compatibility/${comparisonId}`);
}

export function getCompatibilityChanges(comparisonId, filters = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null && value !== "") query.set(key, value);
  }
  return request(`/api/v1/compatibility/${comparisonId}/changes?${query}`);
}

export function getCompatibilitySummary(comparisonId) {
  return request(`/api/v1/compatibility/${comparisonId}/summary`);
}

export async function downloadCompatibilityJSON(comparisonId, retryAfterRefresh = true) {
  let response;
  const headers = new Headers({ Accept: "application/json" });
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/compatibility/${comparisonId}/report/json`, {
      headers,
      credentials: "include",
    });
  } catch {
    throw new Error("Unable to reach the ContractIQ backend.");
  }
  if (response.status === 401 && accessToken) {
    if (retryAfterRefresh) {
      const renewed = await refreshAuthSession().catch(() => null);
      if (renewed) return downloadCompatibilityJSON(comparisonId, false);
    }
    clearAccessToken();
    if (typeof window !== "undefined") window.dispatchEvent(new Event("contractiq:auth-expired"));
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Backend returned HTTP ${response.status}`);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `contractiq-compatibility-${comparisonId}.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function deleteCompatibilityComparison(comparisonId) {
  return request(`/api/v1/compatibility/${comparisonId}`, { method: "DELETE" });
}

export function generateTestCases(specificationId) {
  return request(`/api/v1/specifications/${specificationId}/test-cases/generate`, { method: "POST" });
}

export function getTestCases(specificationId, includeDisabled = true) {
  return request(`/api/v1/specifications/${specificationId}/test-cases?include_disabled=${includeDisabled}`);
}

export function getTestCaseDetails(testCaseId) {
  return request(`/api/v1/test-cases/${testCaseId}`);
}

export function updateTestCase(testCaseId, payload) {
  return request(`/api/v1/test-cases/${testCaseId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function deleteTestCase(testCaseId) {
  return request(`/api/v1/test-cases/${testCaseId}`, { method: "DELETE" });
}

export function executeAllTests(specificationId, payload) {
  return request(`/api/v1/specifications/${specificationId}/test-runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function executeSelectedTests(payload) {
  return request("/api/v1/test-runs/execute-selected", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function getTestRuns(specificationId) {
  return request(`/api/v1/specifications/${specificationId}/test-runs`);
}

export function getTestRunDetails(testRunId) {
  return request(`/api/v1/test-runs/${testRunId}`);
}

export function getTestResults(testRunId) {
  return request(`/api/v1/test-runs/${testRunId}/results`);
}

export function getTestResultDetails(resultId) {
  return request(`/api/v1/test-results/${resultId}`);
}

export function getTestingSummary(specificationId) {
  return request(`/api/v1/specifications/${specificationId}/testing-summary`);
}

function monitoringRequest(path, options = {}) {
  return request(path, options);
}

function queryString(values) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined && value !== null && value !== "") query.set(key, String(value));
  }
  return query.toString();
}

export function getMonitoringConfigurations(projectId) {
  return monitoringRequest(`/api/v1/projects/${projectId}/monitoring/configurations`);
}

export function createMonitoringConfiguration(projectId, payload) {
  return monitoringRequest(`/api/v1/projects/${projectId}/monitoring/configurations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function updateMonitoringConfiguration(projectId, configurationId, payload) {
  return monitoringRequest(`/api/v1/projects/${projectId}/monitoring/configurations/${configurationId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function startMonitoringConfiguration(projectId, configurationId) {
  return monitoringRequest(`/api/v1/projects/${projectId}/monitoring/configurations/${configurationId}/start`, {
    method: "POST",
  });
}

export function pauseMonitoringConfiguration(projectId, configurationId) {
  return monitoringRequest(`/api/v1/projects/${projectId}/monitoring/configurations/${configurationId}/pause`, {
    method: "POST",
  });
}

export function deleteMonitoringConfiguration(projectId, configurationId) {
  return monitoringRequest(`/api/v1/projects/${projectId}/monitoring/configurations/${configurationId}`, {
    method: "DELETE",
  });
}

export function getMonitoringOverview(projectId, window = "1h", environmentName = "") {
  return monitoringRequest(`/api/v1/projects/${projectId}/monitoring/overview?${queryString({ window, environment_name: environmentName })}`);
}

export function getMonitoringMetrics(projectId, window = "1h", endpoint = "", environmentName = "") {
  return monitoringRequest(`/api/v1/projects/${projectId}/monitoring/metrics?${queryString({ window, endpoint, environment_name: environmentName })}`);
}

export function getMonitoringChecks(projectId, filters = {}) {
  return monitoringRequest(`/api/v1/projects/${projectId}/monitoring/checks?${queryString(filters)}`);
}

export function getMonitoringErrors(projectId, filters = {}) {
  return monitoringRequest(`/api/v1/projects/${projectId}/monitoring/errors?${queryString(filters)}`);
}

export function getMonitoringAnomalies(projectId, filters = {}) {
  return monitoringRequest(`/api/v1/projects/${projectId}/monitoring/anomalies?${queryString(filters)}`);
}

export function getAnomalyModelStatus(projectId) {
  return monitoringRequest(`/api/v1/projects/${projectId}/monitoring/anomalies/model`);
}

export function trainAnomalyModel(projectId) {
  return monitoringRequest(`/api/v1/projects/${projectId}/monitoring/anomalies/train`, { method: "POST" });
}

export function acknowledgeAnomaly(projectId, anomalyId) {
  return monitoringRequest(`/api/v1/projects/${projectId}/monitoring/anomalies/${anomalyId}/acknowledge`, {
    method: "PATCH",
  });
}

export function getMonitoringAlerts(projectId, filters = {}) {
  return monitoringRequest(`/api/v1/projects/${projectId}/monitoring/alerts?${queryString(filters)}`);
}

export function updateMonitoringAlert(projectId, alertId, action) {
  return monitoringRequest(`/api/v1/projects/${projectId}/monitoring/alerts/${alertId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  });
}

export function createMonitoringSocket(projectId) {
  const token = getAccessToken();
  if (!token) throw new Error("Sign in again to restore access to the live monitoring stream.");
  const url = new URL(`${API_BASE_URL}/ws/v1/projects/${projectId}/monitoring/live`);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return new WebSocket(url, [
    "contractiq.monitoring.v1",
    `bearer.${token}`,
  ]);
}