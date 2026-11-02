// Thin wrappers around the backend JSON API.

async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`${options.method ?? "GET"} ${path} failed: HTTP ${res.status}`);
  return res.json();
}

export const getHealth = () => request("/api/health");

export const getCards = () => request("/api/cards");

export const validateSpot = (hero, board) =>
  request("/api/spot/validate", { method: "POST", body: JSON.stringify({ hero, board }) });

export const getPresets = () => request("/api/ranges/presets");

/** body: {notation} or {weights}, plus hero/board codes for card removal. */
export const analyseRange = (body) =>
  request("/api/ranges/analyse", { method: "POST", body: JSON.stringify(body) });

export const computeEquity = (body) =>
  request("/api/equity", { method: "POST", body: JSON.stringify(body) });
