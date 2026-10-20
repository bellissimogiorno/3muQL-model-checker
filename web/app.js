/* The page owns interaction and rendering; all logic runs in worker.js. */
import { createSourceHighlighter, sourceSelection } from "./editor.js";
import { createModelView } from "./model-view.js";
import { atomLabel, nameLabel } from "./model-data.js";
import { formulaHTML } from "./notation.js";
import { readProgress, phaseIdentity, elapsedSeconds, duration, deadlineDelay, describeProgress } from "./progress.js";

const $ = (id) => document.getElementById(id);
const LEGACY_DRAFT_KEY = "muql-explorer-draft-v1";
const DRAFT_KEY = `${LEGACY_DRAFT_KEY}:${new URL(".", import.meta.url).pathname}`;
const DRAFT_COPY_PREFIX = `${DRAFT_KEY}:copy:`;
const MAX_DRAFT_COPIES = 20;
const MAX_SOURCE = 250000;
const NEW_THEORY = '# My theory\n\nDescribe your question here. Edit the predicate and claim, then choose Continue to claims.\n\n```muql\ntheory "My theory"\npredicate p/0\nproperty Claim: p\n```\n';
const limitIds = ["max-points", "max-values", "max-stages", "timeout", "max-quorums", "max-frames", "max-nodes", "max-decisions"];
const searchLimitIds = ["max-points", "max-values", "max-stages", "max-quorums", "max-frames"];
const state = { examples: [], example: null, lastCurated: null, editingCurated: false, adjusted: false, sourceAtLoad: "", metadata: null, metadataSource: null, desired: null,
  worker: null, task: null, sequence: 0, timer: null, watchdog: null, results: null, interrupted: null, draftTimer: null, draftEnabled: true, draftReady: false,
  draftBase: null, draftContent: null, draftConflict: false, draftCopyKey: null, loading: true };
const modelViews = new Set();
function clearModelViews() { for (const view of modelViews) view.dispose(); modelViews.clear(); }
const sourceHighlight = createSourceHighlighter({ editor: $("theory-editor"), layer: $("source-highlight"),
  code: $("source-highlight-code"), toggle: $("highlight-syntax"), disclosure: $("source-details") });

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function formulaElement(text, className = "formula") {
  const node = el("code", className);
  // formulaHTML escapes all source characters before adding fixed markup.
  node.innerHTML = formulaHTML(text);
  return node;
}
function setStatus(text) {
  for (const id of ["status-text", "activity-text"]) if ($(id).textContent !== text) $(id).textContent = text;
}
function freshTheory() { return !!state.metadata && state.metadataSource === $("theory-editor").value; }
function restoreFocus(id) {
  // Disabling a focused loading control can send focus to the page body.
  // Restore it only in that case; never interrupt a user who has moved on.
  if (id && document.activeElement === document.body && !$(id).disabled) $(id).focus({ preventScroll: true });
}
function navigateTo(id) {
  const section = $(id);
  if (!section) return;
  if (section.tagName === "DETAILS") section.open = true;
  const target = section.querySelector("h2, summary") || section;
  target.focus({ preventScroll: true });
  section.scrollIntoView({ block: "start", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
}
function selectionPrompt(message, refresh = false) {
  $("selection-prompt").hidden = false;
  $("selection-message").textContent = message;
  $("refresh-choices").hidden = !refresh;
}
function showUpdateChoices() {
  if (state.task || state.loading || !$("theory-editor").value.trim()) return;
  $("selection-prompt").hidden = false;
  $("refresh-choices").hidden = false;
  $("refresh-choices").focus({ preventScroll: true });
  $("selection-prompt").scrollIntoView({ block: "center", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
}
function mode() { return $("mode-check").checked ? "check" : "search"; }
function optionSelection() {
  return {
    properties: [...$("property-options").querySelectorAll("input:checked")].map((input) => input.value),
    drop: [...$("axiom-options").querySelectorAll("input:not(:checked)")].map((input) => input.value),
  };
}
function currentSelection() {
  if (state.metadataSource === $("theory-editor").value && state.metadata) {
    return optionSelection();
  }
  return state.desired || { properties: null, drop: [] };
}
function readLimits(ids = limitIds) {
  return Object.fromEntries(ids.map((id) => [id.replaceAll("-", "_"), Number($(id).value)]));
}
function settings() {
  const active = mode() === "check" ? limitIds.filter((id) => !searchLimitIds.includes(id)) : limitIds;
  return { mode: mode(), solver: $("solver").value,
    limits: readLimits(active),
    ...currentSelection() };
}
function draftContent() {
  // Keep inactive bounds too: switching modes must not erase them.
  return JSON.stringify({ source: $("theory-editor").value, sourceOpen: $("source-details").open,
    highlight: $("highlight-syntax").checked, example: state.example?.id, ...settings(), limits: readLimits() });
}
function beginDraft() {
  try { state.draftBase = localStorage.getItem(DRAFT_KEY); } catch { state.draftBase = null; }
  state.draftContent = null; state.draftConflict = false;
  const copyId = globalThis.crypto?.randomUUID?.()
    || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;
  state.draftCopyKey = DRAFT_COPY_PREFIX + copyId;
}
function saveDraft() {
  // Only custom work is autosaved. Starting or browsing the curated tour
  // must never replace a saved theory that the user has not restored.
  if (!state.draftEnabled || !state.draftReady) return;
  try {
    const content = draftContent();
    // Lifecycle events in an unchanged tab must never rewrite another tab's work.
    if (content === state.draftContent) return;
    if (localStorage.getItem(state.draftCopyKey) === null) {
      let copies = 0;
      const keys = Array.from({ length: localStorage.length }, (_, index) => localStorage.key(index));
      for (const key of keys) {
        if (!key?.startsWith(DRAFT_COPY_PREFIX)) continue;
        // Never remove another tab's copy automatically: even an exact match
        // can change between reading and deleting it in shared localStorage.
        copies++;
      }
      if (copies >= MAX_DRAFT_COPIES) {
        $("draft-status").textContent = "Draft not saved: recovery storage is full. Use Save theory, then keep any recovery copies you need before choosing Forget saved draft.";
        return;
      }
    }
    // A separate key per tab also preserves both copies if two tabs publish at
    // once; localStorage has no atomic compare-and-swap for the shared draft.
    localStorage.setItem(state.draftCopyKey, JSON.stringify({ savedAt: new Date().toISOString(), draft: JSON.parse(content) }));
    const current = localStorage.getItem(DRAFT_KEY);
    state.draftConflict = current !== state.draftBase && current !== content;
    if (!state.draftConflict) {
      localStorage.setItem(DRAFT_KEY, content);
      state.draftBase = content;
    }
    state.draftContent = content;
    $("draft-status").textContent = state.draftConflict
      ? "Another tab changed the saved draft. Your work is kept in a separate recovery copy below."
      : "Draft saved on this device";
    updateDraftOffer();
  } catch { $("draft-status").textContent = "Draft not saved · use Save theory"; }
}
function scheduleSave() {
  clearTimeout(state.draftTimer);
  if (!state.draftEnabled || !state.draftReady) return;
  $("draft-status").textContent = "Saving draft…";
  state.draftTimer = setTimeout(saveDraft, 450);
}
function readDraft() {
  try {
    // Legacy work remains available without deleting another project's draft.
    // A scoped tombstone deliberately suppresses legacy fallback after Forget.
    const draft = JSON.parse(localStorage.getItem(DRAFT_KEY) ?? localStorage.getItem(LEGACY_DRAFT_KEY));
    if (!draft || typeof draft.source !== "string" || draft.source.length > MAX_SOURCE) return null;
    return draft;
  } catch { return null; }
}
function updateDraftOffer() {
  const saved = readDraft();
  $("restore-draft").hidden = !saved || state.draftReady;
  $("custom-draft-status").textContent = !state.draftEnabled ? "Draft saving is off for this visit. Use Save theory to keep your work."
    : state.draftConflict ? "Another tab has a different saved draft. Your open theory is preserved in the recovery copies below. Use Save theory to download it."
      : state.draftReady ? "Your custom theory is open above. Use Save theory to download a copy."
      : saved ? "A saved draft is available on this device. The curated examples leave it unchanged."
        : "Custom work is saved on this device when browser storage is available.";
  const recovery = $("draft-recovery"), actions = $("draft-recovery-actions");
  actions.replaceChildren();
  try {
    const current = localStorage.getItem(DRAFT_KEY);
    const copies = [];
    for (let index = 0; index < localStorage.length; index++) {
      const key = localStorage.key(index);
      if (!key?.startsWith(DRAFT_COPY_PREFIX)) continue;
      try {
        const copy = JSON.parse(localStorage.getItem(key));
        if (typeof copy?.draft?.source === "string" && copy.draft.source.length <= MAX_SOURCE
            && JSON.stringify(copy.draft) !== current) copies.push(copy);
      } catch { /* Ignore damaged recovery records. */ }
    }
    copies.sort((a, b) => String(b.savedAt).localeCompare(String(a.savedAt)));
    for (const [index, copy] of copies.entries()) {
      const restore = el("button", "text-button", `Restore recovery copy ${index + 1}`);
      restore.type = "button"; restore.disabled = !!state.task || state.loading;
      restore.addEventListener("click", () => {
        if (state.task || state.loading || !confirmReplacement("Replace your open theory with this recovery copy?")) return;
        openCustomSource(copy.draft.source, "Recovered draft", copy.draft);
        // Restoring a recovery copy must retain the other tab's main draft.
        state.draftBase = JSON.stringify(copy.draft);
      });
      const button = el("button", "text-button", `Save recovery theory ${index + 1}`);
      button.type = "button";
      button.addEventListener("click", () => download(`muql-recovery-${index + 1}.md`, copy.draft.source, "text/markdown"));
      actions.append(restore, button, el("span", "small-text", `Saved ${copy.savedAt || "in another tab"}`));
    }
    recovery.hidden = copies.length === 0;
    if (state.draftConflict) recovery.open = true;
  } catch { recovery.hidden = true; }
}
function confirmReplacement(message, protectSaved = false) {
  const source = $("theory-editor").value;
  const curated = state.example && source === state.lastCurated?.source;
  if (!curated && source !== state.sourceAtLoad) return window.confirm(message + " Save theory first if you want to keep a separate copy.");
  if (protectSaved && !state.draftReady && readDraft()) return window.confirm("This will replace your saved draft. To keep it, cancel and choose Restore saved draft, then Save theory.");
  return true;
}
function download(filename, content, mime = "text/plain") {
  const url = URL.createObjectURL(new Blob([content], { type: `${mime};charset=utf-8` }));
  const anchor = el("a");
  anchor.href = url; anchor.download = filename; document.body.append(anchor); anchor.click(); anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}
function downloadButton(item, label, id) {
  const button = el("button", "text-button", label || item.label);
  button.type = "button";
  if (id) button.id = id;
  button.addEventListener("click", () => download(item.filename, item.content, item.mime));
  return button;
}
function clearError() { $("error-box").hidden = true; $("error-box").replaceChildren(); }
function showError(error) {
  const data = typeof error === "string" ? { message: error } : error;
  const box = $("error-box");
  box.replaceChildren(el("strong", "", "Please check this before continuing"));
  box.append(el("p", "", data?.message || "Something went wrong. Please try again."));
  if (Number.isInteger(data?.line)) {
    $("source-details").open = true;
    const jump = el("button", "text-button", `Go to line ${data.line}${data.column ? `, column ${data.column}` : ""}`);
    jump.type = "button";
    jump.addEventListener("click", () => {
      $("source-details").open = true;
      const editor = $("theory-editor");
      editor.focus(); editor.setSelectionRange(...sourceSelection(editor.value, data.line, data.column || 1));
      editor.scrollTop = Math.max(0, (data.line - 4) * parseFloat(getComputedStyle(editor).lineHeight));
      sourceHighlight.sync();
    });
    box.append(jump);
  }
  box.hidden = false;
  box.focus({ preventScroll: true });
  box.scrollIntoView({ block: "center", behavior: "auto" });
}
function markStale() {
  $("run-progress").hidden = true;
  if (state.interrupted && !state.interrupted.stale) {
    state.interrupted.stale = true;
    $("results").prepend(el("p", "stale-note", "This progress belongs to the previous interrupted run. The theory or settings have changed; run again for the current experiment."));
    $("result-label").textContent = "Previous interrupted run";
  }
  if (!state.results) return;
  if (state.results.stale) { $("results").querySelector(".previous-results").open = false; return; }
  state.results.stale = true;
  const root = $("results");
  const previous = el("details", "previous-results");
  previous.append(el("summary", "", `Previous run · ${state.results.result.report.theory}`),
    el("p", "stale-note", "These results and downloads belong to the previous run, with the theory, properties, and assumptions recorded below."),
    ...root.children);
  const notice = el("div", "empty-state");
  notice.append(el("h3", "", "No results for the current experiment"),
    el("p", "", "The theory or run settings have changed. Run again to test them. The previous evidence is saved below until the next run."));
  root.replaceChildren(notice, previous);
  $("result-label").textContent = "Previous run";
}
function customTheory(origin) {
  state.example = null; state.adjusted = false;
  $("example-select").value = "";
  $("curated-picker").hidden = true; $("custom-context").hidden = false;
  $("theory-origin").textContent = origin;
  $("custom-context-message").textContent = state.editingCurated
    ? "You are editing a curated example. Undo your source edits to return to it, keeping your current choices and run settings. Reset restores the example’s original source and settings."
    : "You are working on your own theory in the editor below. Save a copy to keep your work, or reset to your last curated example.";
  setExampleText(null);
}
function showCuratedContext() {
  $("example-select").value = state.example.id;
  $("curated-picker").hidden = false; $("custom-context").hidden = true;
  $("theory-origin").textContent = state.adjusted ? `Adjusted example · ${state.example.title}` : state.example.title;
  setExampleText(state.example);
  if (state.adjusted) {
    $("example-description").textContent = "The example’s source is unchanged. Use the properties, assumptions, and run settings below for your experiment, or Reset example to restore its defaults.";
    $("example-hint").textContent = "";
  }
}
function adjustExperiment() {
  if (state.editingCurated && state.lastCurated) state.lastCurated.adjusted = true;
  if (state.example) {
    state.adjusted = true;
    showCuratedContext();
  }
  markStale(); updateControls(); scheduleSave();
}
function invalidateTheory() {
  // The textarea has already changed when input fires. Preserve the visible
  // choices directly, before discarding the old parse; currentSelection()
  // intentionally accepts only choices belonging to the unchanged source.
  if (state.metadata) state.desired = optionSelection();
  state.metadata = null; state.metadataSource = null;
  const curated = state.editingCurated && state.lastCurated;
  const restored = curated && $("theory-editor").value === curated.source;
  if (!state.draftReady && !restored) beginDraft();
  state.draftReady = !restored;
  if (restored) {
    // Source identity is independent of the last download. Undo can return to
    // the same preset even after saving or inspecting an edited version.
    clearTimeout(state.draftTimer);
    state.example = curated.example; state.adjusted = curated.adjusted;
    $("draft-status").textContent = "";
    if (curated.metadata) {
      renderOptions(curated.metadata, state.desired || { properties: null, drop: [] });
      const selected = optionSelection();
      const defaults = { properties: state.example.properties || curated.metadata.properties.map((p) => p.name), drop: state.example.drop || [] };
      // Reading an edited declaration can remove a selected property without a
      // checkbox event. Retain that choice, but describe the restored preset as
      // adjusted whenever its current selection differs from the defaults.
      if (["properties", "drop"].some((key) => selected[key].length !== defaults[key].length || selected[key].some((name) => !defaults[key].includes(name)))) {
        state.adjusted = true; curated.adjusted = true;
      }
    }
    showCuratedContext();
  } else customTheory("Edited theory");
  if (!freshTheory()) {
    $("theory-signature").textContent = "";
    $("theory-options").hidden = true;
    $("loaded-theory").textContent = restored ? "Curated source restored · update choices to continue" : "Edited theory · update choices to continue";
    selectionPrompt("The source has changed. Update the choices here, then review the properties and assumptions before running.", true);
  }
  clearError(); markStale(); updateControls(); updateDraftOffer();
  setStatus(freshTheory() ? "Curated example restored. Your current choices and run settings are kept."
    : $("theory-editor").value.trim() ? "Choices are out of date. Update choices in step 2 before running." : "The source is empty. Enter or load a theory to continue.");
  scheduleSave();
}
function scopeLimitMessage(checking) {
  const scope = state.metadata?.scope;
  if (!scope) return "";
  const sizes = [["values", scope.values.length, "max-values"]];
  if (checking) sizes.push(["participants", scope.points.length, "max-points"],
    ["stages", scope.stages, "max-stages"], ["quorum generators", scope.quorums.length, "max-quorums"]);
  for (const [label, size, id] of sizes) {
    const maximum = Number($(id).max);
    if (size > maximum) {
      const remedy = id === "max-values" ? "Use the Python package, or reduce the declared values."
        : "Choose Search for a model to try smaller frames, or use the Python package.";
      return `This browser demo supports at most ${maximum} ${label}; this theory declares ${size}. ${remedy}`;
    }
  }
  return "";
}
function updateControls() {
  const busy = !!state.task || state.loading;
  const checking = mode() === "check";
  const noFrame = checking && state.metadata && !state.metadata.scope_declared;
  const scopeLimit = scopeLimitMessage(checking);
  const empty = !$("theory-editor").value.trim();
  const fresh = freshTheory();
  $("run-button").disabled = busy || empty || (fresh && (!!noFrame || !!scopeLimit));
  // A stale source makes this a navigation action, so invalid size fields
  // cannot prevent the user reaching the button that refreshes the choices.
  $("run-button").type = fresh ? "submit" : "button";
  $("run-button").setAttribute("aria-controls", fresh ? "results" : "selection-prompt");
  $("continue-settings").disabled = busy || empty;
  $("continue-settings").textContent = fresh ? "Continue to run settings →" : "Update choices to continue →";
  $("continue-settings").setAttribute("aria-controls", fresh ? "configure" : "selection-prompt");
  $("inspect-button").disabled = busy || empty;
  $("refresh-choices").disabled = busy || empty;
  $("continue-theory").disabled = busy || empty;
  $("load-example").disabled = busy || !state.example;
  $("example-select").disabled = busy || !state.examples.length;
  $("run-controls").disabled = busy;
  $("theory-editor").readOnly = busy;
  for (const id of ["import-button", "load-source", "create-theory", "restore-draft"]) $(id).disabled = busy;
  for (const button of $("draft-recovery-actions").querySelectorAll("button")) if (button.textContent.startsWith("Restore")) button.disabled = busy;
  for (const id of ["save-source", "custom-save-source"]) $(id).disabled = state.loading || empty;
  for (const id of ["return-examples", "reset-custom"]) {
    $(id).disabled = busy || !state.lastCurated;
  }
  $("return-examples").textContent = state.lastCurated ? `Reset to ${state.lastCurated.example.title}` : "Reset to curated example";
  $("custom-reset-help").textContent = state.lastCurated
    ? `Reset returns to ${state.lastCurated.example.title} and restores its original source and settings.`
    : "Reset returns to the last curated example and restores its original source and settings.";
  for (const id of ["property-options", "axiom-options"]) $(id).disabled = busy;
  for (const id of ["properties-all", "properties-none", "axioms-all"]) $(id).disabled = busy;
  for (const button of $("symbol-buttons").querySelectorAll("button")) button.disabled = busy;
  $("stop-button").hidden = !state.task;
  $("activity-bar").hidden = !state.task;
  document.body.classList.toggle("is-busy", !!state.task);
  $("status-dot").classList.toggle("busy", busy);
  $("search-bounds").classList.toggle("is-inactive", checking);
  for (const id of searchLimitIds) $(id).disabled = checking;
  const scope = state.metadata?.scope;
  const scopeNote = scopeLimit || (noFrame ? "This theory has no declared frame. Choose Search for a model, or declare participants, values, stages, and quorums in the theory."
    : checking && scope ? `Declared frame: ${scope.points.length} participant${scope.points.length === 1 ? "" : "s"}, ${scope.values.length} value${scope.values.length === 1 ? "" : "s"}, ${scope.stages} time stage${scope.stages === 1 ? "" : "s"}, ${scope.quorums.length} quorum generator${scope.quorums.length === 1 ? "" : "s"}. Unions of these generators are also quorums. The checker finds truth values within this frame.`
      : checking ? "Read the theory to see its declared frame. The checker finds truth values within that frame."
        : "The checker chooses participants, values, stages, and quorums within your limits. Named values and the theory’s time convention are retained.");
  if ($("scope-note").textContent !== scopeNote) $("scope-note").textContent = scopeNote;
  $("bounds-help").textContent = checking ? "Not used in this mode; the theory’s declared frame sets these sizes."
    : "Maximum sizes. Smaller frames are tried first.";
  const selection = currentSelection();
  const modelOnly = selection.properties?.length === 0 || (state.metadata && state.metadata.properties.length === 0);
  $("run-button").textContent = !fresh ? checking ? "Update choices before checking this frame →"
    : modelOnly ? "Update choices before finding an axiom model →" : "Update choices before finding a counterexample →"
    : modelOnly ? "Find an axiom model →" : checking ? "Check this frame →" : "Find a counterexample →";
  if (state.metadata) {
    const properties = selection.properties?.length ?? state.metadata.properties.length;
    const axioms = state.metadata.axioms.length - selection.drop.length;
    $("property-count").textContent = `${properties} of ${state.metadata.properties.length} selected`;
    $("axiom-count").textContent = `${axioms} of ${state.metadata.axioms.length} kept`;
    $("run-summary").textContent = modelOnly ? `No properties selected: find a model of the ${axioms} retained axiom${axioms === 1 ? "" : "s"}.`
      : `Test ${properties} propert${properties === 1 ? "y" : "ies"} against ${axioms} retained axiom${axioms === 1 ? "" : "s"}.`;
    $("run-theory").textContent = `Theory to test: ${state.metadata.name}`;
    $("run-properties").textContent = modelOnly ? "No property will be tested." : `Properties: ${(selection.properties ?? state.metadata.properties.map((p) => p.name)).join(", ")}.`;
    $("run-omissions").textContent = selection.drop.length ? `Removed axioms: ${selection.drop.join(", ")}.` : "All declared axioms are included.";
    $("run-omissions").classList.toggle("has-omissions", selection.drop.length > 0);
  } else {
    $("run-summary").textContent = empty ? "Choose a theory to begin." : "Choices are out of date. The button below takes you to Update choices in step 2.";
    for (const id of ["run-theory", "run-properties", "run-omissions"]) $(id).textContent = "";
    $("run-omissions").classList.toggle("has-omissions", false);
  }
}
function renderOptions(metadata, selection) {
  state.metadata = metadata;
  state.metadataSource = $("theory-editor").value;
  if (state.editingCurated && state.metadataSource === state.lastCurated?.source) state.lastCurated.metadata = metadata;
  $("loaded-theory").textContent = metadata.name;
  $("claims-theory").textContent = `Properties and assumptions of ${metadata.name}`;
  $("theory-signature").textContent = metadata.predicates?.length
    ? `Predicates: ${metadata.predicates.map((p) => `${p.name}/${p.arity}`).join(", ")}. The number gives each predicate’s arity.` : "No predicate symbols declared.";
  $("max-values").min = Math.min(Number($("max-values").max), Math.max(1, metadata.scope.values.length));
  if (Number($("max-values").value) < Number($("max-values").min)) $("max-values").value = $("max-values").min;
  for (const [kind, containerId] of [["properties", "property-options"], ["axioms", "axiom-options"]]) {
    const container = $(containerId);
    container.replaceChildren(el("legend", "sr-only", kind === "axioms" ? "Axioms" : "Properties"));
    if (!metadata[kind].length) container.append(el("p", "small-text", kind === "axioms" ? "No axioms declared." : "No properties declared. A run will look for an axiom model."));
    for (const item of metadata[kind]) {
      const label = el("label", "option-row");
      const input = el("input"); input.type = "checkbox"; input.value = item.name;
      input.checked = kind === "axioms" ? !(selection.drop || []).includes(item.name) : selection.properties == null || selection.properties.includes(item.name);
      const text = el("span"); text.append(el("strong", "", item.name), formulaElement(item.formula));
      label.append(input, text); container.append(label);
      input.addEventListener("change", adjustExperiment);
    }
  }
  $("theory-options").hidden = false; $("selection-prompt").hidden = true;
  $("assumptions-details").open = optionSelection().drop.length > 0;
  updateControls();
}
function progressPanel() {
  const root = el("div", "run-progress"); root.id = "result-progress";
  root.setAttribute("aria-label", "Run progress");
  const nodes = {};
  for (const field of ["phase", "frame", "counts", "findings", "work", "timing", "note"]) {
    nodes[field] = el(field === "phase" ? "h3" : "p", `progress-${field}`);
    root.append(nodes[field]);
  }
  return { root, nodes };
}
function renderProgress(task, announce = true) {
  if (task.type !== "run") return;
  const now = performance.now();
  task.lastProgressRender = now;
  const text = describeProgress(task, now);
  $("run-progress").hidden = false;
  for (const field of ["phase", "frame", "counts", "findings", "work", "timing", "note"]) {
    const controls = $("progress-" + field);
    if (controls.textContent !== text[field]) controls.textContent = text[field];
    controls.hidden = !text[field];
    const result = task.progressNodes?.[field];
    if (result) { if (result.textContent !== text[field]) result.textContent = text[field]; result.hidden = !text[field]; }
  }
  if (state.task === task) {
    $("activity-text").textContent = text.phase;
    $("activity-detail").textContent = text.activity;
    // Only this status is live. Visual clocks can update twice per second
    // without repeatedly interrupting assistive technology.
    if (announce && now - task.lastAnnouncement >= 5000 && text.announcement !== task.lastAnnouncedText) {
      $("status-text").textContent = text.announcement;
      task.lastAnnouncement = now; task.lastAnnouncedText = text.announcement;
    }
  }
}
function armWatchdog(task, startup) {
  if (state.task !== task) return;
  clearTimeout(state.watchdog);
  const elapsed = elapsedSeconds(startup ? task.created : task.started, performance.now());
  // The engine owns the chosen budget. Allow one additional second for its
  // completed report to serialize, but never multiply an unbounded budget.
  const delay = deadlineDelay(startup ? 90 : task.payload.limits.timeout, elapsed, startup ? 0 : 1);
  if (!delay) {
    terminate(startup ? "The browser engine took too long to start. Check your connection and try again." : "The run reached its time limit.", true);
    return;
  }
  state.watchdog = setTimeout(() => armWatchdog(task, startup), delay);
}
function endTask() {
  clearInterval(state.timer); clearTimeout(state.watchdog);
  state.timer = null; state.watchdog = null; state.task = null;
  $("elapsed").textContent = "";
  document.querySelector(".results-panel").setAttribute("aria-busy", "false");
  updateControls();
}
function showInterrupted(task, reason, timeout = false) {
  task.ended = performance.now();
  state.results = null; state.interrupted = task;
  const summary = el("div", "result-summary");
  summary.append(el("h3", "", timeout ? "Incomplete · time limit reached" : "Incomplete · stopped"), el("p", "", reason), el("p", "", "No conclusion was drawn from this interrupted run. Your theory and settings are unchanged."));
  const panel = progressPanel(); task.progressNodes = panel.nodes;
  $("results").replaceChildren(summary, panel.root);
  $("result-label").textContent = "Incomplete";
  renderProgress(task, false);
}
function terminate(reason, timeout = false) {
  const task = state.task;
  if (!task) return;
  state.worker?.terminate(); state.worker = null;
  endTask();
  if (task?.type === "run") {
    showInterrupted(task, reason, timeout);
  } else if (task?.type === "inspect") {
    selectionPrompt("Reading stopped. Update the choices to continue.", true);
  }
  setStatus(reason + " The engine will restart when you try again.");
  $(task?.type === "inspect" ? "continue-theory" : "run-button").focus();
}
function makeWorker() {
  const worker = new Worker(new URL("worker.js", import.meta.url), { type: "module" });
  worker.addEventListener("message", ({ data }) => {
    const task = state.task;
    if (state.worker !== worker || !task || !data || typeof data !== "object" || data.id !== task.id) return;
    if (data.type === "phase") {
      if (typeof data.message !== "string" || task.started !== null) return;
      if (task.phaseMessage !== data.message) task.phaseStarted = performance.now();
      task.phaseMessage = data.message;
      setStatus(data.message);
      renderProgress(task, false);
      return;
    }
    if (data.type === "started") {
      if (task.type !== "run" || task.started !== null) return;
      task.started = performance.now();
      task.phaseStarted = task.started;
      setStatus(task.payload.mode === "check" ? "Checking the declared frame…" : "Searching small frames first…");
      task.lastAnnouncement = task.started;
      renderProgress(task, false);
      armWatchdog(task, false);
      return;
    }
    if (data.type === "progress") {
      if (task.type !== "run" || task.started === null) return;
      const progress = readProgress(data.progress, task.progress);
      if (!progress) return;
      const first = task.progress === null;
      if (!task.progress || phaseIdentity(progress) !== phaseIdentity(task.progress)) task.phaseStarted = performance.now();
      task.progress = progress;
      // A fast search can emit thousands of phase changes. Retain every latest
      // snapshot, but limit DOM work; the clock also paints it within 500ms.
      if (first || performance.now() - task.lastProgressRender >= 100) renderProgress(task);
      return;
    }
    if (data.type !== "result") return;
    endTask();
    $("run-progress").hidden = true;
    if (!data.result?.ok) {
      showError(data.result?.error);
      setStatus("The request could not be completed. Check the message beside the theory.");
      if (task.type === "run") {
        state.results = null;
        $("results").replaceChildren(el("p", "small-text", "No result was produced. Correct the issue above and run again."));
        $("result-label").textContent = "No result";
      } else {
        selectionPrompt("The theory could not be read. Check the message above, then update the choices.", true);
      }
      return;
    }
    if (task.type === "inspect") {
      renderOptions(data.result.metadata, task.selection);
      setStatus("Ready. Choose what to investigate, then run.");
      saveDraft();
      if (task.advance) navigateTo("workspace");
      else restoreFocus(task.returnFocus);
    } else {
      renderResults(data.result, task.payload);
      setStatus("Finished. Inspect the results below.");
      $("results-heading").focus({ preventScroll: true });
      $("results-heading").scrollIntoView({ block: "start", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    }
  });
  worker.addEventListener("error", (event) => {
    event.preventDefault();
    if (state.worker !== worker) return;
    const task = state.task;
    worker.terminate(); state.worker = null; endTask();
    showError("The browser engine stopped unexpectedly. Try a smaller scope, or refresh the page and try again.");
    setStatus("Engine stopped. Your theory is still here.");
    if (task?.type === "run") showInterrupted(task, "The engine stopped before returning a result.");
    else selectionPrompt("Reading stopped. Update the choices to try again.", true);
  });
  return worker;
}
function startTask(type, payload) {
  if (state.task || state.loading) return;
  clearError();
  if (payload.source.length > MAX_SOURCE) { showError("This demo accepts theories up to 250,000 characters. Use the Python package for larger files."); return; }
  if (type === "run" && (!Number.isFinite(payload.limits?.timeout) || payload.limits.timeout <= 0)) {
    showError("Enter a finite number of seconds greater than zero for Stop after.");
    $("timeout").focus();
    return;
  }
  try { state.worker ||= makeWorker(); }
  catch { showError("This browser could not start a module worker. Try a current browser with WebAssembly support."); return; }
  const created = performance.now();
  const task = { id: ++state.sequence, type, payload, selection: currentSelection(), created, started: null,
    phaseStarted: created, progress: null, lastAnnouncement: created, lastAnnouncedText: "" };
  state.task = task;
  $("run-progress").hidden = true;
  $("activity-detail").textContent = "";
  if (type === "run") {
    clearModelViews();
    state.results = null; state.interrupted = null; $("result-label").textContent = "Running";
    const pending = el("div", "empty-state");
    pending.append(el("h3", "", "Looking for evidence…"), el("p", "", "You can stop at any time. A limit or interruption is never counted as a proof."));
    const panel = progressPanel(); task.progressNodes = panel.nodes;
    $("results").replaceChildren(pending, panel.root);
    document.querySelector(".results-panel").setAttribute("aria-busy", "true");
  }
  setStatus(type === "inspect" ? "Reading the theory…" : "Preparing the run…");
  updateControls();
  renderProgress(task, false);
  state.timer = setInterval(() => {
    if (state.task !== task) return;
    $("elapsed").textContent = duration(elapsedSeconds(task.started ?? task.created, performance.now()));
    renderProgress(task);
    if (task.type === "inspect") $("activity-detail").textContent = `Reading elapsed ${duration(elapsedSeconds(task.created, performance.now()))} · separate 90s limit`;
  }, 500);
  armWatchdog(task, true);
  state.worker.postMessage({ id: task.id, type, payload });
}
function inspect(advance = false, returnFocus = null) {
  startTask("inspect", { source: $("theory-editor").value });
  if (state.task?.type === "inspect") { state.task.advance = advance === true; state.task.returnFocus = returnFocus; }
}
function scopeText(scope) {
  if (!scope) return "";
  return `${scope.points?.length || 0} participant(s) · ${scope.values?.length || 0} value(s) · ${scope.stages} time stage(s) · ${scope.time} time`;
}
function scopeBox(scope) {
  const box = el("div", "scope-box");
  box.append(el("p", "", scopeText(scope)));
  if (scope.points) box.append(el("p", "", `Participants: ${scope.points.map(nameLabel).join(", ")}`));
  if (scope.values) box.append(el("p", "", `Values: ${scope.values.map(nameLabel).join(", ")}`));
  const quorums = scope.quorums || scope.quorum_generators;
  if (quorums) box.append(el("p", "", `${scope.quorums ? "Quorums" : "Quorum generators"}: ${quorums.map((q) => `{${q.map(nameLabel).join(", ")}}`).join(" ")}`));
  return box;
}
function valuationTable(rows) {
  const wrapper = el("div");
  const controls = el("div", "download-actions");
  const previous = el("button", "text-button", "Previous rows"); previous.type = "button";
  const next = el("button", "text-button", "Next rows"); next.type = "button";
  const position = el("span", "small-text"); position.setAttribute("aria-live", "polite");
  const scroller = el("div", "table-scroll"); scroller.tabIndex = 0; scroller.setAttribute("role", "region"); scroller.setAttribute("aria-label", "Atomic valuation table, scroll to see more columns");
  const table = el("table", "valuation");
  table.append(el("caption", "", "Complete atomic valuation · t true · b broken · f false"));
  const head = el("thead"); const header = el("tr");
  for (const title of ["Stage", "Participant", "Atom", "Value"]) { const th = el("th", "", title); th.scope = "col"; header.append(th); }
  head.append(header); const body = el("tbody"); table.append(head, body); scroller.append(table);
  let page = 0; const pageSize = 100;
  function render() {
    body.replaceChildren();
    for (const row of rows.slice(page * pageSize, (page + 1) * pageSize)) {
      const tr = el("tr");
      tr.append(el("td", "", row.time), el("td", "", nameLabel(row.point)), el("td", "formula", atomLabel(row.predicate, row.args)));
      const value = el("td"); value.append(el("span", `truth truth-${row.value}`, row.value), document.createTextNode(` ${({ t: "true", b: "broken", f: "false" })[row.value] || ""}`)); tr.append(value); body.append(tr);
    }
    previous.disabled = page === 0; next.disabled = (page + 1) * pageSize >= rows.length;
    position.textContent = `Rows ${rows.length ? page * pageSize + 1 : 0}–${Math.min((page + 1) * pageSize, rows.length)} of ${rows.length}`;
  }
  previous.addEventListener("click", () => { page--; render(); }); next.addEventListener("click", () => { page++; render(); });
  controls.append(previous, position, next); controls.hidden = rows.length <= pageSize;
  wrapper.append(scroller, controls); render(); return wrapper;
}
function modelEvidence(details, model, propertyName = "") {
  const slot = el("div");
  const exact = el("details", "model-exact");
  const exactTitle = el("summary", "", "Full model data");
  exact.append(exactTitle, el("p", "small-text", "All recorded stages, quorums, participants, and atomic values. These data do not change with the diagram controls."), scopeBox(model.scope));
  let loaded = false, tableLoaded = false;
  function showDiagram() {
    if (loaded || !details.open) return;
    loaded = true;
    try {
      const view = createModelView(model, { propertyName, onDownload: download, onShowFullModel: () => {
        exact.open = true; showTable(); exactTitle.focus({ preventScroll: true }); exact.scrollIntoView({ block: "start", behavior: "auto" });
      } });
      modelViews.add(view); slot.append(view);
    } catch {
      slot.append(el("p", "notice", "The diagram could not be displayed. Open the full valuation below to inspect the model.")); exact.open = true;
    }
    showTable();
  }
  function showTable() {
    if (tableLoaded || !exact.open) return;
    tableLoaded = true; exact.append(valuationTable(model.valuation));
  }
  details.addEventListener("toggle", () => { if (details.isConnected) showDiagram(); });
  exact.addEventListener("toggle", () => { if (exact.isConnected) showTable(); });
  details.append(slot, exact); showDiagram();
}
function renderResults(result, request) {
  clearModelViews();
  state.results = { result, request };
  const report = result.report; const properties = report.properties || [];
  const cex = properties.filter((p) => p.countermodel); const unknown = properties.filter((p) => p.status === "unknown");
  const searched = request.mode === "search";
  const incomplete = unknown.length > 0 || report.status === "unknown";
  let title;
  if (report.status === "inconsistent") title = "The axioms have no model here";
  else if (cex.length) title = "Counterexample found";
  else if (incomplete) title = "Incomplete · no conclusion yet";
  else if (!properties.length && report.consistency_model) title = "A model of the axioms";
  else title = searched ? "Holds within bounds" : "Holds in this frame";
  const root = $("results"); root.replaceChildren();
  $("result-label").textContent = searched ? "Bounded search" : "Declared frame";
  const summary = el("div", "result-summary"); summary.append(el("h3", "", title));
  summary.append(el("p", "result-theory", `Theory tested: ${report.theory}`));
  summary.append(el("p", "", properties.length ? `Properties tested: ${properties.map((p) => p.name).join(", ")}.` : "No properties tested; this run asks only for a model of the retained axioms."));
  if (cex.length) summary.append(el("p", "", `${cex.length} ${cex.length === 1 ? "property has" : "properties have"} a concrete, independently replayed counterexample.${incomplete ? " Other questions remain unresolved." : ""}`));
  if (cex.length > 1) summary.append(el("p", "", "Each property has its own counterexample model. Their frames and truth values may differ."));
  if (cex.length) summary.append(el("p", "small-text", "Each counterexample satisfies every retained axiom (t or b) and makes its tested property false (f)."));
  if (properties.some((p) => p.status === "holds")) summary.append(el("p", "", "A property that holds here has been checked only in the stated finite frame or search bounds. This is not an unbounded proof."));
  if (report.reason) summary.append(el("p", "", report.reason));
  if (searched) {
    const b = report.bounds;
    summary.append(el("p", "", `Bounds: ${b.points[0]}–${b.points[1]} participants, ${b.values[0]}–${b.values[1]} values, ${b.stages[0]}–${b.stages[1]} stages; at most ${b.max_quorums} quorums per frame. Time: ${b.time}.`));
  } else summary.append(scopeBox(report.scope));
  const kept = result.metadata.axioms.length;
  summary.append(el("p", "small-text", `${kept} retained axiom(s). ${request.drop.length ? `Removed for this run: ${request.drop.join(", ")}.` : "No axioms removed."}`));
  const configuration = el("details", "run-record");
  configuration.append(el("summary", "", "Settings used for this run"));
  const labels = { max_points: "Participants (maximum)", max_values: "Values (maximum)", max_stages: "Stages (maximum)", timeout: "Time limit (seconds)", max_quorums: "Quorums per frame (maximum)", max_frames: "Frames to try", max_nodes: "Compilation nodes", max_decisions: "Solver decisions" };
  configuration.append(el("p", "", `Mode: ${searched ? "Search for a model" : "Check this frame"}. Requested solver: ${request.solver === "pysat" ? "MiniSat" : "Built-in"}.`));
  for (const [key, value] of Object.entries(request.limits || {})) configuration.append(el("p", "", `${labels[key] || key}: ${value}`));
  configuration.append(el("p", "", `Retained axioms: ${result.metadata.axioms.map((a) => a.name).join(", ") || "none"}.`));
  summary.append(configuration);
  const stats = report.stats || {}; const metrics = el("div", "metrics");
  for (const [label, value] of [["Elapsed", stats.seconds !== undefined ? `${stats.seconds.toFixed(2)} s` : null], ["Frames", stats.frames], ["Solver", stats.solver || stats.backend], ["Decisions", stats.decisions]]) {
    if (value === null || value === undefined) continue;
    const item = el("span"); item.append(el("strong", "", `${label} `), document.createTextNode(String(value))); metrics.append(item);
  }
  summary.append(metrics);
  const downloads = result.downloads || []; const actions = el("div", "download-actions");
  for (const item of downloads.filter((d) => ["report", "theory"].includes(d.name))) actions.append(downloadButton(item, item.name === "report" ? "Download report JSON" : "Download retained theory", item.name === "report" ? "download-report" : "download-retained-theory"));
  summary.append(actions); root.append(summary);
  for (const property of properties) {
    const card = el("article", "property-card"); const heading = el("div", "property-heading");
    const label = ({ counterexample: "Counterexample", holds: searched ? "Holds within bounds" : "Holds in this frame", unknown: "Incomplete", inconsistent: "No axiom model" })[property.status] || property.status;
    heading.append(el("h3", "", property.name), el("span", `badge ${property.status}`, label)); card.append(heading);
    const formula = result.metadata.properties.find((p) => p.name === property.name)?.formula;
    if (formula) card.append(formulaElement(formula, "formula result-formula"));
    if (property.reason) card.append(el("p", "", property.reason));
    if (property.countermodel) {
      const model = property.countermodel; const f = model.failure;
      card.append(el("p", "", `False at stage ${f.time}, participant ${nameLabel(f.point)}, quorum {${f.quorum.map(nameLabel).join(", ")}}. Every retained axiom is satisfied.`));
      const details = el("details", "witness"); details.open = property === cex[0];
      details.append(el("summary", "", "Inspect the counterexample"));
      modelEvidence(details, model, property.name);
      const links = el("div", "download-actions");
      for (const item of downloads.filter((d) => d.name === `witness-${property.name}-theory` || d.name === `witness-${property.name}-countermodel`)) {
        const button = downloadButton(item, item.name.endsWith("-theory") ? "Download counterexample theory" : "Download countermodel JSON");
        button.setAttribute("aria-label", button.textContent + " for " + property.name);
        links.append(button);
      }
      details.append(links); card.append(details);
    }
    root.append(card);
  }
  if (!properties.length && report.consistency_model) {
    const details = el("details", "witness"); details.open = true;
    details.append(el("summary", "", "Inspect the axiom model"));
    modelEvidence(details, { scope: report.consistency_scope || report.scope, valuation: report.consistency_model }); root.append(details);
  }
  if (state.example && $("theory-editor").value === state.lastCurated?.source) {
    const next = state.examples.find((e) => e.id === state.example.next);
    const box = el("div", "next-example"); box.append(el("p", "", "Keep exploring"));
    const button = el("button", "button primary workflow-action", next ? next.title + " →" : "Create your own theory →"); button.type = "button";
    button.addEventListener("click", () => { if (next) loadExample(next); else navigateTo("custom-experiment"); });
    box.append(button); root.append(box);
  }
}
function setExampleText(example) {
  $("example-description").textContent = example?.description || "Your own theory. Edit the declarations and choose what to investigate.";
  $("example-hint").textContent = example?.hint || "";
}
function applySettings(data) {
  $("mode-check").checked = data.mode === "check";
  $("mode-search").checked = data.mode !== "check";
  for (const id of limitIds) {
    const value = data.limits?.[id.replaceAll("-", "_")];
    const maximum = $(id).max === "" ? Infinity : Number($(id).max);
    if (typeof value === "number" && Number.isFinite(value) && value >= Number($(id).min) && value <= maximum && (id !== "timeout" || value > 0)) $(id).value = value;
  }
  $("solver").value = data.solver === "pysat" ? "pysat" : "builtin";
}
async function fetchText(url) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 30000);
  try {
    const response = await fetch(url, { cache: "no-cache", signal: controller.signal });
    if (!response.ok) throw new Error(`Could not load the file (HTTP ${response.status}). Check your connection and try again.`);
    return await response.text();
  } catch (error) {
    if (error.name === "AbortError") throw new Error("The download took too long. Check your connection and try again.");
    throw error;
  } finally { clearTimeout(timer); }
}
async function fetchJSON(url) { return JSON.parse(await fetchText(url)); }
async function loadExample(example, initial = false, moveFocus = true) {
  // A selection is a request to load, never a second preview state. Until the
  // fetch succeeds, every visible identity continues to describe the old source.
  $("example-select").value = state.example?.id || "";
  if (state.task || state.loading || !example) return;
  if (!initial && !confirmReplacement("Replace your edited theory with this example?")) return;
  // Save the latest custom edit before loading can suppress draft writes.
  if (state.draftReady) saveDraft();
  const returnFocus = !moveFocus && ["example-select", "load-example"].includes(document.activeElement?.id) ? document.activeElement.id : null;
  state.loading = true; updateControls(); setStatus("Loading the example…"); clearError();
  let successfulLoad = false;
  try {
    const source = await fetchText(new URL(example.file, import.meta.url));
    state.example = example; state.adjusted = false;
    $("theory-editor").value = source; $("theory-editor").scrollTop = 0;
    state.lastCurated = { example, source: $("theory-editor").value, metadata: null, adjusted: false };
    state.editingCurated = true;
    state.sourceAtLoad = $("theory-editor").value; state.draftReady = false;
    $("draft-status").textContent = "";
    showCuratedContext();
    updateDraftOffer();
    sourceHighlight.refresh();
    $("source-details").open = false;
    $("loaded-theory").textContent = "Reading the loaded theory…";
    $("theory-signature").textContent = "";
    state.metadata = null; state.metadataSource = null;
    state.desired = { properties: example.properties || null, drop: example.drop || [] };
    $("max-values").min = 1;
    applySettings({ mode: example.mode, limits: { max_points: 1, max_values: 2, max_stages: 1, timeout: 10, max_quorums: 8, max_frames: 500, max_nodes: 500000, max_decisions: 100000, ...example.bounds } });
    $("theory-options").hidden = true; selectionPrompt("Reading properties and assumptions…");
    markStale(); successfulLoad = true;
  } catch (error) { showError(error.message); setStatus("Example not loaded. Your previous theory is unchanged."); }
  finally { state.loading = false; updateControls(); }
  if (successfulLoad) { if (!initial && moveFocus) navigateTo("choose"); inspect(false, returnFocus); }
}
$("run-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (state.task || state.loading) return;
  if (!freshTheory()) { showUpdateChoices(); return; }
  if ((mode() === "check" && !state.metadata.scope_declared) || scopeLimitMessage(mode() === "check") || !$("run-form").reportValidity()) return;
  saveDraft(); startTask("run", { source: $("theory-editor").value, ...settings() });
});
$("run-button").addEventListener("click", () => { if (!freshTheory()) showUpdateChoices(); });
$("stop-button").addEventListener("click", () => terminate("Stopped at your request."));
$("floating-stop").addEventListener("click", () => terminate("Stopped at your request."));
$("inspect-button").addEventListener("click", inspect);
$("refresh-choices").addEventListener("click", () => inspect(true));
$("continue-theory").addEventListener("click", () => { if (freshTheory()) navigateTo("workspace"); else inspect(true); });
$("continue-settings").addEventListener("click", () => {
  if (state.task || state.loading || !$("theory-editor").value.trim()) return;
  if (freshTheory()) navigateTo("configure"); else showUpdateChoices();
});
$("run-form").addEventListener("invalid", (event) => { const details = event.target.closest("details"); if (details) details.open = true; }, true);
$("load-example").addEventListener("click", () => loadExample(state.example, false, false));
$("example-select").addEventListener("change", () => {
  const example = state.examples.find((e) => e.id === $("example-select").value);
  return loadExample(example, false, false);
});
$("theory-editor").addEventListener("input", invalidateTheory);
$("highlight-syntax").addEventListener("change", scheduleSave);
for (const input of $("run-controls").querySelectorAll("input,select")) {
  // Numeric input changes the experiment before focus leaves the field.
  for (const event of ["input", "change"]) input.addEventListener(event, adjustExperiment);
}
for (const [id, container, checked] of [["properties-all", "property-options", true], ["properties-none", "property-options", false], ["axioms-all", "axiom-options", true]]) {
  $(id).addEventListener("click", () => { for (const input of $(container).querySelectorAll("input")) input.checked = checked; adjustExperiment(); });
}
function saveTheory() {
  if (state.loading || !$("theory-editor").value.trim()) return;
  const source = $("theory-editor").value;
  saveDraft();
  download("muql-theory.md", source, "text/markdown");
  state.sourceAtLoad = source;
}
for (const id of ["save-source", "custom-save-source"]) $(id).addEventListener("click", saveTheory);
for (const id of ["import-button", "load-source"]) $(id).addEventListener("click", () => $("import-file").click());
for (const id of ["return-examples", "reset-custom"]) $(id).addEventListener("click", () => loadExample(state.lastCurated?.example));
function openCustomSource(source, origin, draft = {}, modified = false) {
  beginDraft();
  state.editingCurated = false;
  $("theory-editor").value = source; $("theory-editor").scrollTop = 0;
  state.sourceAtLoad = modified ? "" : $("theory-editor").value; state.metadata = null; state.metadataSource = null;
  state.desired = { properties: Array.isArray(draft.properties) ? draft.properties.filter((x) => typeof x === "string") : null,
    drop: Array.isArray(draft.drop) ? draft.drop.filter((x) => typeof x === "string") : [] };
  if (!$("highlight-syntax").disabled) $("highlight-syntax").checked = draft.highlight !== false;
  $("max-values").min = 1;
  applySettings({ ...draft, mode: draft.mode === "check" ? "check" : "search", limits: { max_points: 1, max_values: 2, max_stages: 1, timeout: 10, max_quorums: 8, max_frames: 500, max_nodes: 500000, max_decisions: 100000, ...draft.limits } });
  sourceHighlight.refresh(); $("source-details").open = true;
  invalidateTheory(); customTheory(origin); updateDraftOffer();
  navigateTo("choose"); $("theory-editor").focus({ preventScroll: true }); inspect();
}
$("create-theory").addEventListener("click", () => {
  if (state.task || state.loading || !confirmReplacement("Replace your edited theory with a new theory?", true)) return;
  openCustomSource(NEW_THEORY, "New custom theory", {}, true);
});
$("restore-draft").addEventListener("click", () => {
  if (state.task || state.loading) return;
  const draft = readDraft();
  if (!draft) { updateDraftOffer(); return; }
  if (!confirmReplacement("Replace your edited theory with the saved draft?")) return;
  openCustomSource(draft.source, "Saved draft", draft);
  $("draft-status").textContent = "Restored your saved draft";
});
$("import-file").addEventListener("change", async () => {
  const file = $("import-file").files[0]; $("import-file").value = "";
  if (!file || state.task || state.loading) return;
  if (file.size > MAX_SOURCE * 4) { showError("This file is too large for the browser demo. Use the Python package for large files."); return; }
  if (!confirmReplacement("Replace the edited theory with this file?", true)) return;
  state.loading = true; updateControls();
  let imported = false;
  try {
    const source = await file.text();
    if (source.length > MAX_SOURCE) { showError("This demo accepts theories up to 250,000 characters."); return; }
    beginDraft();
    $("theory-editor").value = source; state.sourceAtLoad = $("theory-editor").value; state.example = null; state.editingCurated = false;
    // A different file starts a new investigation; edits to this file will
    // preserve its own choices once it has been read.
    state.metadata = null; state.metadataSource = null; state.desired = null;
    sourceHighlight.refresh();
    $("source-details").open = true;
    invalidateTheory(); customTheory(`Opened file: ${file.name}`); updateDraftOffer(); imported = true;
  } catch { showError("The file could not be opened. Please try it again."); }
  finally { state.loading = false; updateControls(); }
  if (imported) { navigateTo("choose"); inspect(); }
});
$("forget-draft").addEventListener("click", () => {
  clearTimeout(state.draftTimer); state.draftEnabled = false;
  try {
    const keys = Array.from({ length: localStorage.length }, (_, index) => localStorage.key(index));
    for (const key of keys) if (key?.startsWith(DRAFT_COPY_PREFIX)) localStorage.removeItem(key);
    localStorage.setItem(DRAFT_KEY, JSON.stringify({ forgotten: true }));
    updateDraftOffer(); $("draft-status").textContent = "Draft saving off for this visit"; setStatus("Saved draft and recovery copies for this page removed. The open theory is unchanged.");
  }
  catch { setStatus("This browser does not allow access to saved drafts."); }
});
const symbolButtons = [...$("symbol-buttons").querySelectorAll("button[data-symbol]")];
for (const button of symbolButtons) {
  button.addEventListener("focus", () => {
    for (const item of symbolButtons) item.tabIndex = item === button ? 0 : -1;
    $("symbol-description").textContent = button.dataset.description;
  });
  button.addEventListener("pointerenter", () => { $("symbol-description").textContent = button.dataset.description; });
  button.addEventListener("keydown", (event) => {
    const index = symbolButtons.indexOf(button);
    let next;
    if (event.key === "ArrowRight") next = (index + 1) % symbolButtons.length;
    else if (event.key === "ArrowLeft") next = (index - 1 + symbolButtons.length) % symbolButtons.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = symbolButtons.length - 1;
    else return;
    event.preventDefault(); symbolButtons[next].focus();
  });
  button.addEventListener("click", () => {
    const editor = $("theory-editor");
    if (editor.readOnly) return;
    const scrollTop = editor.scrollTop;
    editor.setRangeText(button.dataset.symbol, editor.selectionStart, editor.selectionEnd, "end");
    editor.focus({ preventScroll: true }); editor.scrollTop = scrollTop;
    editor.dispatchEvent(new Event("input", { bubbles: true }));
  });
}
for (const link of document.querySelectorAll('a[href^="#"]')) {
  link.addEventListener("click", (event) => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const id = link.getAttribute("href").slice(1);
    if ($(id)) { event.preventDefault(); navigateTo(id); }
  });
}
let scrollPending = false;
function updateStepNavigation() {
  const sections = [...document.querySelectorAll(".workflow-step")];
  let active = sections[0]?.id;
  for (const section of sections) if (section.getBoundingClientRect().top <= 180) active = section.id;
  if (window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 8) active = sections.at(-1)?.id;
  for (const link of document.querySelectorAll(".workflow-nav a")) {
    if (link.getAttribute("href") === `#${active}`) link.setAttribute("aria-current", "step"); else link.removeAttribute("aria-current");
  }
  scrollPending = false;
}
window.addEventListener("scroll", () => { if (!scrollPending) { scrollPending = true; requestAnimationFrame(updateStepNavigation); } }, { passive: true });
$("source-details").addEventListener("toggle", () => { if (!state.loading && $("theory-editor").value) scheduleSave(); });
function flushDraft() { if (!state.loading) saveDraft(); }
window.addEventListener("beforeunload", flushDraft);
window.addEventListener("pagehide", flushDraft);
document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") flushDraft(); });
window.addEventListener("storage", (event) => {
  if (event.key === DRAFT_KEY || event.key?.startsWith(DRAFT_COPY_PREFIX)) updateDraftOffer();
});

async function initialize() {
  if (location.protocol === "file:") throw new Error("From the package directory, run bash serve.sh (or bash serve.sh --python python if that is your Python 3 command), then open the printed address, normally http://127.0.0.1:8000/.");
  const config = await fetchJSON(new URL("config.json", import.meta.url));
  $("version").textContent = `v${config.version}`;
  state.examples = await fetchJSON(new URL(config.examples, import.meta.url));
  $("example-select").replaceChildren();
  const groups = new Map();
  for (const example of state.examples) {
    if (!groups.has(example.group)) { const group = el("optgroup"); group.label = example.group; groups.set(example.group, group); $("example-select").append(group); }
    const option = el("option", "", example.title); option.value = example.id; groups.get(example.group).append(option);
  }
  state.loading = false;
  updateDraftOffer();
  await loadExample(state.examples[0], true);
}
updateControls();
initialize().catch((error) => { state.loading = false; updateControls(); $("boot-error").textContent = `The demo could not load. ${error.message} Refresh the page to try again.`; $("boot-error").hidden = false; setStatus("Demo unavailable. See the message above."); });
