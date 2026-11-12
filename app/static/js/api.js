// Backend access (ADR 0025). The same operations are available two ways:
//
// - "server":  the FastAPI app (`uv run uvicorn app.main:app`), over HTTP under api/;
// - "browser": the same Python engine running inside this page with Pyodide
//              (Python compiled to WebAssembly), in a Web Worker so the page stays
//              responsive. This is what the static GitHub Pages site uses.
//
// The mode is detected once: if api/health answers with JSON we use the server,
// otherwise the in-browser engine.

const ROUTES = {
  health: ["GET", "api/health"],
  cards: ["GET", "api/cards"],
  presets: ["GET", "api/ranges/presets"],
  validate_spot: ["POST", "api/spot/validate"],
  analyse_range: ["POST", "api/ranges/analyse"],
  equity: ["POST", "api/equity"],
  analyse: ["POST", "api/analyse"],
};

const statusListeners = new Set();
/** Listen for backend status messages, e.g. "Loading NumPy…" while Pyodide starts. */
export function onBackendStatus(fn) {
  statusListeners.add(fn);
}
const emitStatus = (text) => statusListeners.forEach((fn) => fn(text));

async function serverAvailable() {
  try {
    const res = await fetch(ROUTES.health[1], { cache: "no-store" });
    return res.ok && (res.headers.get("content-type") ?? "").includes("json");
  } catch {
    return false;
  }
}

function serverBackend() {
  return {
    mode: "server",
    async call(op, args = {}) {
      const [method, path] = ROUTES[op];
      const res = await fetch(path, {
        method,
        headers: { "Content-Type": "application/json" },
        body: method === "POST" ? JSON.stringify(args) : undefined,
      });
      if (!res.ok) throw new Error(`${method} ${path} failed: HTTP ${res.status}`);
      return res.json();
    },
  };
}

function browserBackend() {
  const worker = new Worker(new URL("./pyworker.js", import.meta.url), { type: "module" });
  const pending = new Map();
  let nextId = 0;
  worker.onmessage = ({ data }) => {
    if (data.type === "status") return emitStatus(data.text);
    const entry = pending.get(data.id);
    if (!entry) return;
    pending.delete(data.id);
    if (data.error) entry.reject(new Error(data.error));
    else entry.resolve(data.result);
  };
  worker.onerror = (e) => emitStatus(`Engine failed to start: ${e.message ?? e}`);
  return {
    mode: "browser",
    call(op, args = {}) {
      return new Promise((resolve, reject) => {
        const id = nextId++;
        pending.set(id, { resolve, reject });
        worker.postMessage({ id, op, args });
      });
    },
  };
}

let backendPromise = null;
/** The active backend ({mode, call}); created on first use. */
export function backend() {
  backendPromise ??= serverAvailable().then((ok) => (ok ? serverBackend() : browserBackend()));
  return backendPromise;
}

const call = async (op, args) => (await backend()).call(op, args);

export const getHealth = () => call("health");
export const getCards = () => call("cards");
export const getPresets = () => call("presets");
export const validateSpot = (hero, board) => call("validate_spot", { hero, board });
/** body: {notation} or {weights}, plus hero/board codes for card removal. */
export const analyseRange = (body) => call("analyse_range", body);
export const computeEquity = (body) => call("equity", body);
export const analyseDecision = (body) => call("analyse", body);
