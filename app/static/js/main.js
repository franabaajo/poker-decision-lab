// Entry point for the frontend. Plain ES modules, no build step (ADR 0006).

async function checkApi() {
  const pill = document.getElementById("api-status");
  try {
    const res = await fetch("/api/health");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    pill.textContent = `API: ok · v${data.version}`;
    pill.className = "pill pill--ok";
  } catch (err) {
    pill.textContent = "API: unreachable";
    pill.className = "pill pill--down";
    console.error("Health check failed:", err);
  }
}

checkApi();
