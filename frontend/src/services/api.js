const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();

if (!configuredBaseUrl) {
  throw new Error("VITE_API_BASE_URL is not configured. Add it to frontend/.env.");
}

const API_BASE_URL = configuredBaseUrl.replace(/\/$/, "");

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