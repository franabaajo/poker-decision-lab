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
