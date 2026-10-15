/* Linked, read-only views of an independently replayed finite model. */
import { atomLabel, createModelIndex, valueAt } from "./model-data.js";
import { modelDiagramSvg, POINTS_PER_PAGE, ATOMS_PER_PAGE } from "./model-svg.js";

const TRUTH = { t: "true", b: "broken", f: "false" };
const STAGES_PER_PAGE = 12;
let serial = 0;
function el(tag, className = "", text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function button(text, action, className = "button secondary") {
  const node = el("button", className, text); node.type = "button";
  node.addEventListener("click", action); return node;
}
function field(text, control) {
  const wrapper = el("div"); const label = el("label", "", text);
  control.id = `model-control-${++serial}`; label.htmlFor = control.id;
  wrapper.append(label, control); return wrapper;
}

export function createModelView(model, { propertyName = "", onDownload, onShowFullModel } = {}) {
  const root = el("section", "model-view");
  const heading = el("h4", "model-title", "Explore this model"); heading.id = `model-view-${++serial}`;
  root.setAttribute("aria-labelledby", heading.id);
  root.append(heading);
  root.dispose = () => {};
  const index = createModelIndex(model);
  if (!index.valid) {
    root.append(el("p", "notice", "A diagram is unavailable for this model. The full valuation and downloads remain available below."));
    return root;
  }
  const failure = index.failure;
  let time = failure?.time ?? 0, quorumIndex = failure?.quorumIndex ?? 0;
  // Start with the first atom page at the recorded stage. Distinct witnesses
  // often share a frame and their first atom, but differ in the remaining atoms.
  let atomKey = null;
  let atomStart = 0, filterQuery = "";
  let pointStart = failure ? Math.floor(index.pointNames.indexOf(failure.point) / POINTS_PER_PAGE) * POINTS_PER_PAGE : 0;
  let disposed = false, pending = null, lastDiagram = null, imageWidth = 0, imageTextScale = 1;
  const count = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
  const modelSummary = el("div", "model-summary");
  const scopeSummary = el("p", "model-scope");
  scopeSummary.append(el("strong", "", "Whole model"), document.createTextNode(": " + [count(index.pointNames.length, "participant"), count(index.scope.quorums.length, "quorum"), count(index.scope.stages, "stage"), count(index.atoms.length, "atom"), count(index.scope.values.length, "value")].join(" · ")));
  modelSummary.append(scopeSummary);
  if (onShowFullModel) modelSummary.append(button("Full model data", onShowFullModel, "text-button"));
  root.append(modelSummary);
  const description = el("p", "model-intro", "The diagram shows one stage and highlights one quorum. Its page may show only some participants or atoms. The controls change this view of the same model.");
  root.append(description);
  if (!index.complete) root.append(el("p", "notice", "Some recorded data are missing or inconsistent. Unlisted atomic values appear as ‘?’; see the full valuation below."));

  const failureBar = el("div", model.failure == null ? "model-context" : "model-failure");
  const failureText = failure ? `Recorded failure${propertyName ? " of " + propertyName : ""}: stage ${failure.time}, participant ${failure.point}, quorum Q${failure.quorumIndex + 1}. The property is false at this context.`
    : model.failure != null ? "The recorded failure context is unavailable. Inspect the complete report for details." : "This model satisfies all retained axioms.";
  failureBar.append(el("p", "", failureText));
  const restore = button("Return to failing context", () => {
    time = failure.time; quorumIndex = failure.quorumIndex;
    pointStart = Math.floor(index.pointNames.indexOf(failure.point) / POINTS_PER_PAGE) * POINTS_PER_PAGE;
    update();
  }, "text-button");
  if (failure) failureBar.append(restore);
  root.append(failureBar);

  const viewHeading = el("h5", "model-view-heading", "Choose a diagram view"); viewHeading.id = `model-view-options-${++serial}`; root.append(viewHeading);
  const controls = el("div", "model-controls"); controls.setAttribute("role", "group"); controls.setAttribute("aria-labelledby", viewHeading.id);
  const atomSelect = el("select"); atomSelect.className = "model-atom";
  const atomField = field("Atoms shown", atomSelect); atomField.className = "model-atom-field";
  const choicesNote = el("p", "small-text model-choice-note");
  function populateAtoms(query = "") {
    const queryText = query.trim().toLocaleLowerCase();
    const matched = queryText ? index.atoms.filter(atom => atom.label.toLocaleLowerCase().includes(queryText)) : index.atoms;
    const shown = matched.slice(0, 100);
    const current = atomKey === null ? null : index.atoms.find(atom => atom.key === atomKey);
    if (current && !shown.includes(current)) shown.unshift(current);
    atomSelect.replaceChildren();
    const all = el("option", "", index.atoms.length ? index.atoms.length > ATOMS_PER_PAGE ? "All atoms (paged)" : "All atoms" : "No atomic predicates listed"); all.value = ""; atomSelect.append(all);
    for (const atom of shown) { const option = el("option", "", atom.label); option.value = atom.key; atomSelect.append(option); }
    atomSelect.value = atomKey ?? "";
    choicesNote.textContent = matched.length > 100 ? `Showing the first 100 of ${matched.length} matches. Refine the search to find another atom.`
      : !matched.length && index.atoms.length ? `No matching atoms.${current ? " The current atom remains selected." : ""}` : "";
  }
  if (index.atoms.length > 20) {
    const search = el("input"); search.type = "search"; search.placeholder = "Predicate or argument";
    search.addEventListener("input", () => { filterQuery = search.value; populateAtoms(filterQuery); });
    const filterField = field("Find an atom", search); filterField.className = "model-filter"; root.append(filterField);
  }
  populateAtoms(); atomSelect.disabled = !index.atoms.length;
  atomSelect.addEventListener("change", () => {
    atomKey = atomSelect.value || null;
    if (atomKey !== null) atomStart = Math.floor(index.atoms.findIndex(atom => atom.key === atomKey) / ATOMS_PER_PAGE) * ATOMS_PER_PAGE;
    update();
  });
  const stageSelect = el("select"); stageSelect.className = "model-stage";
  // The browser bridge bounds stages. A numeric control also supports larger imported scopes without a huge option list.
  const stageInput = index.scope.stages <= 200 ? stageSelect : el("input");
  if (stageInput === stageSelect) {
    for (let t = 0; t < index.scope.stages; t++) { const option = el("option", "", String(t)); option.value = String(t); stageSelect.append(option); }
  } else { stageInput.type = "number"; stageInput.min = "0"; stageInput.max = String(index.scope.stages - 1); stageInput.step = "1"; }
  stageInput.disabled = index.scope.stages === 1;
  stageInput.addEventListener("change", () => {
    const value = stageInput.value.trim(), next = Number(value);
    if (value && Number.isSafeInteger(next) && next >= 0 && next < index.scope.stages) time = next;
    update();
  });
  const quorumSelect = el("select"); quorumSelect.className = "model-quorum";
  index.scope.quorums.forEach((members, q) => {
    const memberNames = members.map(point => atomLabel(point, [])).join(", ");
    const label = memberNames.length <= 40 ? `{${memberNames}}` : `${members.length} participants`;
    const option = el("option", "", `Q${q + 1} · ${label}${q === failure?.quorumIndex ? " · failure quorum" : ""}`);
    option.value = String(q); quorumSelect.append(option);
  });
  quorumSelect.disabled = index.scope.quorums.length === 1;
  quorumSelect.addEventListener("change", () => { quorumIndex = Number(quorumSelect.value); update(); });
  controls.append(field("Stage", stageInput), atomField, field("Quorum highlighted", quorumSelect));
  root.append(controls, choicesNote);
  const viewSummary = el("p", "model-view-summary"); root.append(viewSummary);
  if (index.scope.quorums.length > 1) root.append(el("p", "small-text model-view-help", "Changing the highlighted quorum changes membership lines; atomic truth values stay the same."));
  const legend = el("div", "model-legend");
  for (const [value, word] of Object.entries(TRUTH)) { const item = el("span"); item.append(el("strong", `truth truth-${value}`, value), document.createTextNode(word)); legend.append(item); }
  root.append(legend);

  const quorumSummary = el("div", "model-quorum-summary");
  const quorumHeading = el("p", "model-quorum-heading");
  const quorumMembers = el("p", "model-quorum-members");
  const quorumNote = el("p", "model-quorum-note");
  quorumSummary.append(quorumHeading, quorumMembers, quorumNote); root.append(quorumSummary);

  const figure = el("figure", "model-figure");
  const mapFrame = el("div", "model-map-frame"); mapFrame.tabIndex = 0; mapFrame.setAttribute("role", "region"); mapFrame.setAttribute("aria-label", "Current diagram view; scroll if needed at larger text sizes");
  const map = el("img", "model-map"); map.draggable = false;
  const caption = el("figcaption", "model-caption");
  mapFrame.append(map); figure.append(mapFrame, caption); root.append(figure);
  const pointControls = el("div", "model-pager");
  const previousPoints = button("Previous participants", () => { pointStart = Math.max(0, pointStart - POINTS_PER_PAGE); update(); }, "text-button");
  const nextPoints = button("Next participants", () => { pointStart += POINTS_PER_PAGE; update(); }, "text-button");
  const pointPosition = el("span", "small-text");
  pointControls.append(previousPoints, pointPosition, nextPoints); pointControls.hidden = index.pointNames.length <= POINTS_PER_PAGE; root.append(pointControls);

  const stageControls = el("div", "model-pager");
  const previousStage = button("Previous stage", () => { time--; update(); });
  const nextStage = button("Next stage", () => { time++; update(); });
  const stagePosition = el("span", "small-text");
  stageControls.append(previousStage, stagePosition, nextStage); stageControls.hidden = index.scope.stages === 1; root.append(stageControls);
  const boundary = el("p", "small-text model-boundary"); root.append(boundary);

  // One page selection drives both the overview and its accessible table.
  // Keep it outside <details> so every diagram page is always reachable.
  const atomPager = el("div", "model-pager");
  const previousAtoms = button("Previous atoms", () => { atomKey = null; atomStart = Math.max(0, atomStart - ATOMS_PER_PAGE); update(); }, "text-button");
  const nextAtoms = button("Next atoms", () => { atomKey = null; atomStart += ATOMS_PER_PAGE; update(); }, "text-button");
  const atomPosition = el("span", "small-text"); atomPager.append(previousAtoms, atomPosition, nextAtoms); root.append(atomPager);

  const actions = el("div", "download-actions");
  actions.append(button("Download this view (SVG)", () => {
    if (!lastDiagram) return;
    const filename = `model-stage-${time}-Q${quorumIndex + 1}.svg`;
    if (onDownload) onDownload(filename, lastDiagram.svg, "image/svg+xml");
    else {
      const url = URL.createObjectURL(new Blob([lastDiagram.svg], { type: "image/svg+xml;charset=utf-8" }));
      const a = el("a"); a.href = url; a.download = filename; a.click(); setTimeout(() => URL.revokeObjectURL(url), 10000);
    }
  }, "text-button"));
  actions.append(el("span", "small-text", "Saves only the current diagram view. Full model data are available separately.")); root.append(actions);

  const snapshot = el("details", "model-snapshot-details"); snapshot.open = true;
  const snapshotTitle = el("summary", "", "Atom values at this stage"); snapshot.append(snapshotTitle);
  const snapshotScroll = el("div", "table-scroll"); snapshotScroll.tabIndex = 0; snapshotScroll.setAttribute("role", "region"); snapshotScroll.setAttribute("aria-label", "Atomic values at the selected stage; scroll to see more participants");
  const snapshotTable = el("table", "model-timeline model-snapshot"); snapshotScroll.append(snapshotTable); snapshot.append(snapshotScroll);
  snapshot.append(el("p", "small-text", "This table lists the current atom page, including when the diagram shows just one atom. Select a name to focus the diagram on it.")); root.append(snapshot);

  const traceHint = el("p", "small-text model-trace-hint", "Choose an individual atom to inspect its values across time."); root.append(traceHint);

  const timeline = el("details", "model-time-details"); timeline.open = true;
  timeline.append(el("summary", "", "Selected atom across time"));
  const timelineScroll = el("div", "table-scroll model-timeline-scroll"); timelineScroll.tabIndex = 0; timelineScroll.setAttribute("role", "region"); timelineScroll.setAttribute("aria-label", "Atomic values across time; scroll to see more stages");
  const table = el("table", "model-timeline"); timelineScroll.append(table); timeline.append(timelineScroll); root.append(timeline);
  const timelineNote = el("p", "small-text"); timeline.append(timelineNote);
  const status = el("p", "sr-only"); status.setAttribute("role", "status"); status.setAttribute("aria-live", "polite"); root.append(status);


  function drawMap() {
    if (disposed) return;
    const measured = figure.getBoundingClientRect().width;
    imageWidth = measured > 0 ? measured : 800;
    const textScale = parseFloat(getComputedStyle(root).fontSize) / 16 || 1;
    imageTextScale = textScale;
    lastDiagram = modelDiagramSvg(index, { atomKey, atomStart, time, quorumIndex, pointStart, width: imageWidth, textScale, propertyName });
    map.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(lastDiagram.svg);
    map.alt = lastDiagram.description; map.width = lastDiagram.width; map.height = lastDiagram.height;
    map.style.width = `${lastDiagram.width}px`;
  }
  function queueDraw() { if (pending === null) pending = requestAnimationFrame(() => { pending = null; drawMap(); }); }
  function update() {
    const focusedStage = table.contains(document.activeElement) ? document.activeElement?.getAttribute("data-stage") : null;
    const focusedAtom = snapshotTable.contains(document.activeElement) ? document.activeElement?.getAttribute("data-atom-index") : null;
    atomSelect.value = atomKey ?? "";
    stageInput.value = String(time); quorumSelect.value = String(quorumIndex);
    const points = index.pointNames.slice(pointStart, pointStart + POINTS_PER_PAGE);
    const participantRange = `Participants ${pointStart + 1}–${pointStart + points.length} of ${index.pointNames.length}`;
    const atomRange = index.atoms.length ? `Atoms ${atomStart + 1}–${Math.min(atomStart + ATOMS_PER_PAGE, index.atoms.length)} of ${index.atoms.length}` : "No recorded atoms";
    viewSummary.textContent = `Showing 1 of ${count(index.scope.stages, "stage")} · 1 of ${count(index.scope.quorums.length, "quorum")} · ${participantRange} · ${atomKey === null ? atomRange : `1 of ${count(index.atoms.length, "atom")} shown`}`;
    const matchingFailure = !!failure && time === failure.time && quorumIndex === failure.quorumIndex;
    restore.disabled = matchingFailure && points.includes(failure.point);
    const members = index.scope.quorums[quorumIndex];
    const visibleMembers = points.filter(point => index.quorumMembers[quorumIndex].has(point)).length;
    const otherPageMembers = members.length - visibleMembers;
    quorumHeading.textContent = `Selected quorum Q${quorumIndex + 1}`;
    quorumMembers.textContent = `Q${quorumIndex + 1} = {${members.map(point => atomLabel(point, [])).join(", ")}}`;
    quorumNote.textContent = `${count(members.length, "participant")} in this set${otherPageMembers ? ` · ${visibleMembers} shown here · ${otherPageMembers} on other participant pages` : " · all shown below"}.`;
    caption.replaceChildren();
    if (failure) caption.append(el("p", "", matchingFailure
      ? points.includes(failure.point) ? `The dashed outline marks the recorded property failure at ${failure.point}.` : "The recorded failure is on another participant page."
      : "Exploring another context. Use Return to failing context to see the recorded property failure."));
    pointPosition.textContent = participantRange;
    previousPoints.disabled = pointStart === 0; nextPoints.disabled = pointStart + POINTS_PER_PAGE >= index.pointNames.length;
    previousStage.disabled = time === 0; nextStage.disabled = time === index.scope.stages - 1;
    stagePosition.textContent = `Stage ${time} · ${index.scope.stages} stages in the model`;
    boundary.textContent = index.scope.time === "stutter" ? `Stuttering time: the final stage (${index.scope.stages - 1}) has itself as its successor.`
      : `Finite time: the final stage (${index.scope.stages - 1}) has no successor.`;
    previousAtoms.disabled = atomStart === 0; nextAtoms.disabled = atomStart + ATOMS_PER_PAGE >= index.atoms.length;
    atomPosition.textContent = atomRange;
    atomPager.hidden = index.atoms.length <= ATOMS_PER_PAGE;
    snapshot.hidden = index.atoms.length <= 1;
    snapshotTitle.textContent = `Atom values at stage ${time}`;
    if (!snapshot.hidden) {
      const sh = el("thead"), hr = el("tr"), corner = el("th", "", "Atom"); corner.scope = "col"; hr.append(corner);
      for (const point of points) { const th = el("th", "", point); th.scope = "col"; hr.append(th); }
      sh.append(hr); const sb = el("tbody");
      index.atoms.slice(atomStart, atomStart + ATOMS_PER_PAGE).forEach((atom, i) => {
        const row = el("tr", atom.key === atomKey ? "model-current-stage" : ""); const th = el("th"); th.scope = "row";
        const choose = button(atom.label, () => { atomKey = atom.key; populateAtoms(filterQuery); update(); }, "model-atom-button");
        choose.setAttribute("data-atom-index", String(atomStart + i)); choose.setAttribute("aria-label", `Inspect atom: ${atom.label}`); choose.setAttribute("aria-pressed", String(atom.key === atomKey));
        th.append(choose); row.append(th);
        for (const point of points) {
          const v = valueAt(index, atom.key, time, point); const td = el("td");
          const label = el("span", v ? `truth truth-${v}` : "truth", v || "?"); label.setAttribute("aria-label", v ? `${v}, ${TRUTH[v]}` : "Value not listed");
          td.append(label); row.append(td);
        }
        sb.append(row);
      });
      snapshotTable.replaceChildren(el("caption", "", `Stage ${time} · ${participantRange} · ${atomRange}`), sh, sb);
      if (focusedAtom !== null) (snapshotTable.querySelector(`[data-atom-index="${focusedAtom}"]`) || atomSelect).focus({ preventScroll: true });
    }
    timeline.hidden = index.scope.stages === 1 || atomKey === null;
    traceHint.hidden = index.scope.stages === 1 || !index.atoms.length || atomKey !== null;
    if (!timeline.hidden) {
      const stageStart = Math.floor(time / STAGES_PER_PAGE) * STAGES_PER_PAGE;
      const stageEnd = Math.min(stageStart + STAGES_PER_PAGE, index.scope.stages);
      const head = el("thead"), header = el("tr");
      const corner = el("th", "", "Participant"); corner.scope = "col"; header.append(corner);
      for (let t = stageStart; t < stageEnd; t++) {
        const th = el("th"); th.scope = "col";
        const selectStage = button(String(t), () => { time = t; update(); }, "model-time-button");
        selectStage.setAttribute("data-stage", String(t));
        selectStage.setAttribute("aria-label", `View stage ${t}`); selectStage.setAttribute("aria-pressed", String(t === time));
        th.append(selectStage); header.append(th);
      }
      head.append(header); const body = el("tbody");
      for (const point of points) {
        const row = el("tr"); const th = el("th", "", point); th.scope = "row"; row.append(th);
        for (let t = stageStart; t < stageEnd; t++) {
          const v = valueAt(index, atomKey, t, point); const td = el("td", t === time ? "model-current-stage" : "");
          const label = el("span", v ? `truth truth-${v}` : "truth", v || "?");
          label.setAttribute("aria-label", v ? `${v}, ${TRUTH[v]}` : "Value not listed"); td.append(label); row.append(td);
        }
        body.append(row);
      }
      table.replaceChildren(el("caption", "", `${index.atoms.find(atom => atom.key === atomKey)?.label || "Atomic values"} · ${participantRange}`), head, body);
      if (focusedStage !== null) (table.querySelector(`[data-stage="${focusedStage}"]`) || stageInput).focus({ preventScroll: true });
      timelineNote.textContent = `Showing stages ${stageStart}–${stageEnd - 1} of ${index.scope.stages} stages. ` + (index.scope.stages > STAGES_PER_PAGE ? "Choose a stage above to move through the trace." : "Select a column heading to view that stage in the diagram.");
    } else table.replaceChildren();
    status.textContent = `View at stage ${time}, quorum Q${quorumIndex + 1}. ${viewSummary.textContent}. ${matchingFailure ? "Recorded failure context." : ""}`;
    drawMap();
  }
  update(); queueDraw();
  let observer;
  if (typeof ResizeObserver === "function") {
    observer = new ResizeObserver(() => {
      const scale = parseFloat(getComputedStyle(root).fontSize) / 16 || 1;
      if (Math.abs(figure.getBoundingClientRect().width - imageWidth) > 1 || scale !== imageTextScale) queueDraw();
    }); observer.observe(figure);
  } else window.addEventListener("resize", queueDraw);
  root.dispose = () => { disposed = true; observer?.disconnect(); window.removeEventListener("resize", queueDraw); if (pending !== null) cancelAnimationFrame(pending); };
  return root;
}
