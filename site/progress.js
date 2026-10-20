/* Progress is a partial observation, never a completed checking result. */
const phases = new Set(["validating", "enumerating", "frame", "compiling", "consistency", "property", "replaying", "frame_done", "preparing_results"]);
const counters = ["frames_completed", "frames_consistent", "frames_inconsistent", "frames_unknown", "counterexamples_found"];
const numbers = [...counters, "frame", "points", "values", "stages", "quorums", "variables", "clauses", "decisions"];
const positive = new Set(["frame", "points", "values", "stages", "quorums"]);

export function readProgress(value, previous = null) {
  if (!value || typeof value !== "object" || Array.isArray(value) || !phases.has(value.phase)) return null;
  const result = { phase: value.phase };
  for (const field of numbers) {
    if (!Object.hasOwn(value, field)) continue;
    if (!Number.isSafeInteger(value[field]) || value[field] < (positive.has(field) ? 1 : 0)) return null;
    if (counters.includes(field) && previous?.[field] !== undefined && value[field] < previous[field]) return null;
    result[field] = value[field];
  }
  if (Object.hasOwn(value, "property")) {
    if (typeof value.property !== "string" || !value.property.length) return null;
    result.property = value.property;
  }
  return result;
}

export function phaseIdentity(progress) {
  return JSON.stringify([progress.phase, progress.frame ?? null, progress.property ?? null,
    progress.points ?? null, progress.values ?? null, progress.stages ?? null, progress.quorums ?? null]);
}

export function elapsedSeconds(start, now) {
  return Math.max(0, (now - start) / 1000);
}

export function duration(seconds) {
  const whole = Math.floor(Math.max(0, seconds));
  if (whole < 60) return `${whole}s`;
  if (whole < 3600) return `${Math.floor(whole / 60)}m ${whole % 60}s`;
  return `${Math.floor(whole / 3600)}h ${Math.floor((whole % 3600) / 60)}m ${whole % 60}s`;
}

// Calculate in seconds before converting a bounded slice to milliseconds.
// A finite positive user budget may be much larger than setTimeout's range.
export function deadlineDelay(limit, elapsed, allowance = 0) {
  const remaining = limit - elapsed;
  const seconds = remaining > 0 ? Math.min(60, remaining) : Math.min(60, allowance + remaining);
  return seconds <= 0 ? 0 : Math.max(1, seconds * 1000);
}

export function describeProgress(task, now) {
  const progress = task.progress;
  const searching = task.payload.mode !== "check";
  const ended = task.ended !== undefined;
  const time = ended ? task.ended : now;
  const started = task.started !== null;
  const elapsed = elapsedSeconds(started ? task.started : task.created, time);
  const phaseElapsed = duration(elapsedSeconds(task.phaseStarted, time));
  const property = progress?.property;
  const shortProperty = property?.length > 120 ? `${property.slice(0, 117)}…` : property;
  const labels = {
    validating: "Reading and validating the theory",
    enumerating: "Choosing the next finite frame",
    frame: "Preparing the current frame",
    compiling: "Building the frame's logical constraints",
    consistency: "Checking whether the axioms have a model",
    property: shortProperty ? `Checking property “${shortProperty}”` : "Checking a property",
    replaying: "Independently verifying a candidate model",
    frame_done: searching ? "Frame checked; preparing the next step" : "Finishing the declared-frame check",
    preparing_results: "Preparing reports and downloads",
  };
  const phase = progress ? labels[progress.phase] : started
    ? searching ? "Starting the finite-frame search" : "Starting the declared-frame check"
    : task.phaseMessage || "Preparing the browser engine";
  const shape = [];
  for (const [field, singular, plural] of [["points", "participant", "participants"], ["values", "value", "values"], ["stages", "time stage", "time stages"], ["quorums", "quorum", "quorums"]]) {
    if (progress?.[field] !== undefined) shape.push(`${progress[field]} ${progress[field] === 1 ? singular : plural}`);
  }
  const frameLabel = progress?.phase === "enumerating" && !progress.frame ? "Candidate size" : searching && progress?.frame ? `Frame ${progress.frame}` : "Current frame";
  const frame = shape.length ? `${frameLabel}: ${shape.join(" · ")}` : "";
  const counts = [];
  if (progress?.frames_completed !== undefined) counts.push(`${progress.frames_completed} frame${progress.frames_completed === 1 ? "" : "s"} completed`);
  if (progress?.frames_consistent !== undefined) counts.push(`${progress.frames_consistent} frame${progress.frames_consistent === 1 ? "" : "s"} with an axiom model`);
  if (progress?.frames_inconsistent !== undefined) counts.push(`${progress.frames_inconsistent} inconsistent`);
  if (progress?.frames_unknown !== undefined) counts.push(`${progress.frames_unknown} with incomplete checks`);
  const findings = progress?.counterexamples_found !== undefined
    ? `Verified counterexamples reported: ${progress.counterexamples_found}` : "No verified counterexample update yet.";
  const work = [];
  for (const [field, label] of [["variables", "solver variables"], ["clauses", "clauses"], ["decisions", "solver decisions"]]) {
    if (progress?.[field] !== undefined) work.push(`${progress[field]} ${label}`);
  }
  const timing = started
    ? `Run elapsed ${duration(elapsed)} · chosen limit ${task.payload.limits.timeout}s · ${phaseElapsed} in this phase`
    : `Startup elapsed ${duration(elapsed)} of its separate 90s limit · chosen run limit ${task.payload.limits.timeout}s starts after loading · ${phaseElapsed} in this phase`;
  const note = ended
    ? "Incomplete. This is the last progress update, not a completed result. No downloadable witness or report was returned."
    : "Progress only. Keep the run going for its complete result and downloadable evidence."
      + (progress?.frames_unknown && progress?.frames_consistent ? " A frame with an axiom model can also have incomplete checks." : "");
  return {
    phase: ended ? `Last phase: ${phase}` : phase, frame, counts: counts.join(" · "), findings, work: work.join(" · "), timing, note,
    announcement: [phase, counts[0], progress?.counterexamples_found ? `${progress.counterexamples_found} verified counterexamples reported` : ""].filter(Boolean).join(". "),
    activity: [counts[0], `${started ? "run" : "startup"} ${duration(elapsed)}`, started ? `limit ${task.payload.limits.timeout}s` : "separate 90s startup limit"].filter(Boolean).join(" · "),
  };
}
