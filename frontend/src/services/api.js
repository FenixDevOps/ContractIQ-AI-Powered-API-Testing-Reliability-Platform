const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();

if (!configuredBaseUrl) {
  throw new Error("VITE_API_BASE_URL is not configured. Add it to frontend/.env.");
}

const API_BASE_URL = configuredBaseUrl.replace(/\/$/, "");
export const API_DOCS_URL = `${API_BASE_URL}/docs`;

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

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, options);
  } catch (error) {
    throw new Error("Unable to reach the ContractIQ backend.");
  }
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || `Backend returned HTTP ${response.status}`);
  }
  return payload;
}

export function getProjects() {
  return request("/api/v1/projects");
}

export function createProject(payload) {
  return request("/api/v1/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
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

export async function downloadCompatibilityJSON(comparisonId) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/compatibility/${comparisonId}/report/json`, {
      headers: { Accept: "application/json" },
    });
  } catch {
    throw new Error("Unable to reach the ContractIQ backend.");
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