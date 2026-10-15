/**
 * Mock protocol tests for the actual web/worker.js source.
 *
 * Run: node --experimental-vm-modules tests/browser/worker-protocol.cjs
 *
 * Node's built-in VM supplies a fake worker, network, and Pyodide runtime.
 * These tests verify JavaScript lifecycle and transport behavior; they do not
 * download or execute WebAssembly and are not browser integration tests.
 */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

if (typeof vm.SyntheticModule !== "function") {
  throw new Error("Run these mock tests with node --experimental-vm-modules tests/browser/worker-protocol.cjs");
}

const workerFile = path.resolve(__dirname, "../../web/worker.js");
const source = fs.readFileSync(workerFile, "utf8");
const mockVersion = "0.0.0-mock";

async function fixture(options = {}) {
  const messages = [], calls = [], python = [], packages = [], downloads = [], imports = [], requests = [];
  let listener, starts = 0;
  const self = {
    location: { href: "https://example.test/muql-explorer/worker.js" },
    postMessage(message) { messages.push(message); calls.push(message.type); },
    addEventListener(type, callback) {
      assert.equal(type, "message");
      listener = callback;
    },
  };
  const runtime = {
    unpackArchive(buffer, format, opts) {
      assert.equal(format, "zip");
      assert.equal(opts.extractDir, "/home/pyodide");
      calls.push("unpack");
    },
    runPython(code) {
      python.push(code);
      if (options.probeFailure && code.includes("muql.backends")) throw new Error("private self-check traceback");
    },
    pyimport(name) {
      imports.push(name);
      if (name === "muql") return { __version__: options.engineVersion || mockVersion, destroy() {} };
      assert.equal(name, "muql.web");
      return {
        handle_json(json) {
          calls.push("bridge");
          requests.push(JSON.parse(json));
          if (options.bridgeFailure) throw new Error("private Python traceback");
          if (Object.hasOwn(options, "rawResult")) return options.rawResult;
          return JSON.stringify(options.result || { ok: true, metadata: { source: requests.at(-1).source } });
        },
      };
    },
    async loadPackage(name) {
      packages.push(name);
      if (options.packageFailure) throw new Error("private package traceback");
    },
  };
  const context = vm.createContext({
    self, URL, console: { error() {} },
    fetch: async (url) => {
      downloads.push(String(url));
      if (options.gate) await options.gate;
      if (options.networkFailure) throw new Error("private network traceback");
      if (options.httpFailure) return { ok: false, status: 503 };
      return {
        ok: true,
        async json() {
          if (options.configFailure) throw new SyntaxError("private JSON parse error");
          return { version: mockVersion, engine: "assets/engine.zip", pyodide: "https://cdn.example/pyodide/" };
        },
        async arrayBuffer() { return new ArrayBuffer(0); },
      };
    },
  });
  const module = new vm.SyntheticModule(["loadPyodide"], function () {
    this.setExport("loadPyodide", async ({ indexURL }) => {
      assert.equal(indexURL, "https://cdn.example/pyodide/");
      starts++;
      if (options.runtimeFailure) throw new Error("private WebAssembly traceback");
      return runtime;
    });
  }, { context });
  await module.link(() => {});
  await module.evaluate();
  const script = new vm.Script(source, {
    filename: workerFile,
    importModuleDynamically: async (specifier) => {
      assert.equal(specifier, "https://cdn.example/pyodide/pyodide.mjs");
      return module;
    },
  });
  script.runInContext(context);
  return {
    messages, calls, python, packages, downloads, imports, requests,
    starts: () => starts,
    raw: (data) => listener({ data }),
    send: (type = "inspect", payload = { source: "theory" }, id = 1) => listener({ data: { id, type, payload } }),
  };
}

test("mock worker: startup is lazy, project-relative, and reused", async () => {
  const f = await fixture();
  assert.equal(f.starts(), 0);
  assert.equal(f.downloads.length, 0);
  await f.send();
  assert.equal(f.messages.at(-1).result.ok, true);
  assert.equal(f.messages.some((m) => m.type === "started"), false);
  assert.equal(f.packages.length, 0);
  assert.deepEqual(f.downloads, [
    "https://example.test/muql-explorer/config.json",
    "https://example.test/muql-explorer/assets/engine.zip",
  ]);
  await f.send("run", { source: "theory", solver: "builtin" }, "next");
  assert.equal(f.starts(), 1);
  assert.deepEqual(f.calls.slice(-3), ["started", "bridge", "result"]);
  assert.equal(f.messages.at(-1).id, "next");
  assert.deepEqual(f.imports, ["muql", "muql.web"]);
});

test("mock worker: Unicode theory is JSON data and cannot replace the action", async () => {
  const text = "∀ v. P(v) ⇀ Q(v)\n'); raise RuntimeError('must not execute')\n</script>";
  const f = await fixture();
  await f.send("inspect", { source: text, action: "run" });
  assert.equal(f.requests[0].source, text);
  assert.equal(f.requests[0].action, "inspect");
  assert.equal(f.python.some((code) => code.includes(text)), false);
  assert.equal(f.messages.at(-1).result.metadata.source, text);
});

test("mock worker: native solver downloads once, only when selected for a run", async () => {
  const f = await fixture();
  await f.send("inspect", { source: "theory", solver: "pysat" });
  await f.send("run", { source: "theory", solver: "builtin" }, 2);
  assert.equal(f.packages.length, 0);
  await f.send("run", { source: "theory", solver: "pysat" }, 3);
  await f.send("run", { source: "theory", solver: "pysat" }, 4);
  assert.deepEqual(f.packages, ["python-sat"]);
  assert.equal(f.python.filter((code) => code.includes("muql.backends")).length, 1);
  assert.equal(f.messages.at(-1).result.ok, true);
});

for (const failure of ["packageFailure", "probeFailure"]) {
  test(`mock worker: ${failure} offers built-in retry without silently changing solver`, async () => {
    const f = await fixture({ [failure]: true });
    await f.send("run", { source: "theory", solver: "pysat" });
    assert.equal(f.messages.at(-1).result.ok, false);
    assert.match(f.messages.at(-1).result.error.message, /built-in/);
    assert.equal(f.messages.some((m) => m.type === "started"), false);
    assert.equal(f.requests.length, 0);
    await f.send("run", { source: "theory", solver: "builtin" }, 2);
    assert.equal(f.messages.at(-1).result.ok, true);
    assert.equal(f.requests[0].solver, "builtin");
  });
}

test("mock worker: a mismatched release never reaches the bridge", async () => {
  const f = await fixture({ engineVersion: "different-release" });
  await f.send();
  assert.match(f.messages.at(-1).result.error.message, /different versions/);
  assert.equal(f.calls.includes("bridge"), false);
});

test("mock worker: an overlapping request is rejected without disrupting startup", async () => {
  let release;
  const f = await fixture({ gate: new Promise((resolve) => { release = resolve; }) });
  const pending = f.send();
  await f.send("run", { source: "second" }, 2);
  assert.equal(f.messages.at(-1).id, 2);
  assert.match(f.messages.at(-1).result.error.message, /already running/);
  release();
  await pending;
  assert.equal(f.messages.at(-1).id, 1);
  assert.equal(f.messages.at(-1).result.ok, true);
  assert.equal(f.requests.length, 1);
});

for (const [failure, expected] of [
  ["networkFailure", /connection/],
  ["httpFailure", /HTTP 503/],
  ["configFailure", /configuration/],
  ["runtimeFailure", /browser runtime/],
]) {
  test(`mock worker: ${failure} is readable and a later request can retry`, async () => {
    const options = { [failure]: true };
    const f = await fixture(options);
    await f.send();
    assert.equal(f.messages.at(-1).result.ok, false);
    assert.match(f.messages.at(-1).result.error.message, expected);
    assert.doesNotMatch(f.messages.at(-1).result.error.message, /private|traceback/);
    options[failure] = false;
    await f.send("inspect", { source: "retry" }, 2);
    assert.equal(f.messages.at(-1).result.ok, true);
  });
}

test("mock worker: parser error location is preserved", async () => {
  const expected = { ok: false, error: { message: "line 4: invalid formula", line: 4, column: 7 } };
  const f = await fixture({ result: expected });
  await f.send();
  assert.equal(JSON.stringify(f.messages.at(-1).result), JSON.stringify(expected));
});

test("mock worker: unexpected bridge failures are sanitized and release the busy guard", async () => {
  const options = { bridgeFailure: true };
  const f = await fixture(options);
  await f.send();
  assert.equal(f.messages.at(-1).result.ok, false);
  assert.doesNotMatch(f.messages.at(-1).result.error.message, /private|traceback/);
  options.bridgeFailure = false;
  await f.send("inspect", { source: "retry" }, 2);
  assert.equal(f.messages.at(-1).result.ok, true);
});

test("mock worker: malformed bridge responses cannot be reported as successes", async () => {
  for (const rawResult of ["not JSON", "null", "{}", '{"ok":"true"}']) {
    const f = await fixture({ rawResult });
    await f.send();
    assert.equal(f.messages.at(-1).result.ok, false);
  }
});

test("mock worker: malformed requests do not initialize the runtime", async () => {
  const f = await fixture();
  for (const request of [null, [], { id: 1, type: "eval", payload: {} }, { id: 2, type: "run", payload: null }]) {
    await f.raw(request);
    assert.equal(f.messages.at(-1).result.ok, false);
  }
  assert.equal(f.starts(), 0);
  assert.equal(f.downloads.length, 0);
});
