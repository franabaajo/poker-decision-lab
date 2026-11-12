// Web Worker that runs the Python engine in the browser with Pyodide (ADR 0025).
//
// It loads Pyodide and NumPy from the jsDelivr CDN, then the `pokerlab` package from
// pokerlab.zip (built by scripts/build_site.py), and answers requests by calling
// pokerlab.service.dispatch(operation, json_args) -> json_result.

import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v314.0.2/full/pyodide.mjs";

const status = (text) => postMessage({ type: "status", text });

const ready = (async () => {
  status("Starting Python in your browser…");
  const pyodide = await loadPyodide();
  status("Loading NumPy…");
  await pyodide.loadPackage("numpy");
  status("Loading the poker engine…");
  const res = await fetch(new URL("../pokerlab.zip", import.meta.url));
  if (!res.ok) throw new Error(`Could not download pokerlab.zip (HTTP ${res.status})`);
  pyodide.unpackArchive(await res.arrayBuffer(), "zip", { extractDir: "/home/pyodide/lib" });
  pyodide.runPython("import sys; sys.path.insert(0, '/home/pyodide/lib')");
  const service = pyodide.pyimport("pokerlab.service");
  status("ready");
  return service;
})();

ready.catch((err) => status(`Engine failed to start: ${err.message ?? err}`));

onmessage = async ({ data }) => {
  const { id, op, args } = data;
  try {
    const service = await ready;
    const out = service.dispatch(op, JSON.stringify(args ?? {}));
    postMessage({ type: "result", id, result: JSON.parse(out) });
  } catch (err) {
    postMessage({ type: "result", id, error: String(err.message ?? err) });
  }
};
