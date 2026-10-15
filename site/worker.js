/*
 * 3μQL's Python engine lives in this module worker. Theory text is passed as
 * JSON to the package's parser; it is never evaluated as Python or JavaScript.
 * Terminating this worker is the application's cancellation mechanism.
 */

let runtimePromise = null;
let solverReady = false;
let busy = false;

class UserMessage extends Error {}

function phase(id, message) {
  self.postMessage({ id, type: "phase", message });
}

function reply(id, result) {
  self.postMessage({ id, type: "result", result });
}

function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

async function fetchFile(url, description) {
  let response;
  try {
    response = await fetch(url, { cache: "no-cache" });
  } catch (error) {
    console.error(`3μQL: could not fetch ${description}`, error);
    throw new UserMessage(
      `Could not download ${description}. Check your connection and try again.`,
    );
  }
  if (!response.ok) {
    throw new UserMessage(
      `Could not download ${description} (HTTP ${response.status}). ` +
      "Refresh the page and try again.",
    );
  }
  return response;
}

async function initialize(id) {
  phase(id, "Loading the browser runtime. The first visit may take a moment…");
  const configURL = new URL("config.json", self.location.href);
  const response = await fetchFile(configURL, "the demo configuration");
  let config;
  try {
    config = await response.json();
    if (
      !isRecord(config) || typeof config.version !== "string" ||
      typeof config.engine !== "string" || typeof config.pyodide !== "string"
    ) {
      throw new Error("Incomplete configuration");
    }
  } catch (error) {
    console.error("3μQL: invalid configuration", error);
    throw new UserMessage("The demo configuration is incomplete. Refresh the page and try again.");
  }

  let pyodide;
  try {
    const indexURL = new URL(config.pyodide, configURL);
    if (!indexURL.pathname.endsWith("/")) indexURL.pathname += "/";
    const { loadPyodide } = await import(new URL("pyodide.mjs", indexURL).href);
    pyodide = await loadPyodide({ indexURL: indexURL.href });
  } catch (error) {
    console.error("3μQL: browser runtime could not start", error);
    throw new UserMessage(
      "The browser runtime could not start. Check your connection, then try again. " +
      "This demo needs a browser with WebAssembly and module worker support.",
    );
  }

  phase(id, "Loading the 3μQL engine…");
  const archive = await fetchFile(new URL(config.engine, configURL), "the 3μQL engine");
  try {
    pyodide.unpackArchive(await archive.arrayBuffer(), "zip", { extractDir: "/home/pyodide" });
    // This fixed setup code contains no user-supplied text or configuration.
    pyodide.runPython("import sys\nif '/home/pyodide' not in sys.path:\n    sys.path.insert(0, '/home/pyodide')");
    const muql = pyodide.pyimport("muql");
    let version;
    try {
      version = muql.__version__;
    } finally {
      muql.destroy();
    }
    if (version !== config.version) {
      throw new UserMessage(
        "The page and engine have different versions. Refresh the page to load the current release.",
      );
    }
    const bridge = pyodide.pyimport("muql.web");
    // Retain the module and callable for the lifetime of the worker. They are
    // released with the runtime when the user stops a calculation.
    return { pyodide, bridge, handleJSON: bridge.handle_json };
  } catch (error) {
    if (error instanceof UserMessage) throw error;
    console.error("3μQL: engine could not start", error);
    throw new UserMessage("The 3μQL engine could not start. Refresh the page and try again.");
  }
}

async function runtime(id) {
  if (runtimePromise === null) {
    runtimePromise = initialize(id).catch((error) => {
      runtimePromise = null;
      throw error;
    });
  }
  return runtimePromise;
}

async function prepareSolver(engine, id) {
  if (solverReady) return;
  phase(id, "Loading the accelerated solver…");
  try {
    await engine.pyodide.loadPackage("python-sat");
    // Exercise the actual package backend, including its bounded MiniSat API,
    // before accepting it. No theory text is interpolated into this code.
    engine.pyodide.runPython(`
from muql.backends import solve as _muql_solver_check
_muql_sat = _muql_solver_check(2, [(1, 2), (-1, 2)], timeout=5, max_decisions=1000, backend="pysat")
_muql_unsat = _muql_solver_check(1, [(1,), (-1,)], timeout=5, max_decisions=1000, backend="pysat")
if _muql_sat.status != "sat" or not _muql_sat.assignment.get(2) or _muql_unsat.status != "unsat":
    raise RuntimeError("Accelerated solver self-check failed")
del _muql_solver_check, _muql_sat, _muql_unsat
`);
    solverReady = true;
  } catch (error) {
    console.error("3μQL: accelerated solver is unavailable", error);
    throw new UserMessage(
      "The accelerated solver could not be loaded in this browser. " +
      "Choose the built-in solver and run again.",
    );
  }
}

self.addEventListener("message", async (event) => {
  const request = event.data;
  const id = isRecord(request) ? request.id : null;
  if (
    !isRecord(request) ||
    !(typeof id === "string" || (typeof id === "number" && Number.isFinite(id))) ||
    !["inspect", "run"].includes(request.type) || !isRecord(request.payload)
  ) {
    reply(id, { ok: false, error: { message: "This request could not be read. Refresh the page and try again." } });
    return;
  }
  if (busy) {
    reply(id, { ok: false, error: { message: "A calculation is already running. Stop it or wait for it to finish." } });
    return;
  }

  busy = true;
  try {
    const engine = await runtime(id);
    if (request.type === "run" && request.payload.solver === "pysat") {
      await prepareSolver(engine, id);
    }
    const input = JSON.stringify({ ...request.payload, action: request.type });
    // The page starts its calculation deadline here, after downloads and setup.
    if (request.type === "run") self.postMessage({ id, type: "started" });
    const result = JSON.parse(engine.handleJSON(input));
    if (!isRecord(result) || typeof result.ok !== "boolean") {
      throw new Error("The engine returned an invalid response");
    }
    reply(id, result);
  } catch (error) {
    if (!(error instanceof UserMessage)) console.error("3μQL: worker request failed", error);
    reply(id, {
      ok: false,
      error: { message: error instanceof UserMessage ? error.message :
        "The calculation could not be completed. Try a smaller scope, or refresh the page and try again." },
    });
  } finally {
    busy = false;
  }
});
