/* A deterministic, standalone picture of recorded facts; no logic is evaluated here. */
import { atomLabel, valueAt } from "./model-data.js";

export const POINTS_PER_PAGE = 6;
export const ATOMS_PER_PAGE = 12;
const truth = { t: ["true", "#236241", "#eaf6ee"], b: ["broken", "#805116", "#fff5e4"], f: ["false", "#a52a35", "#fff2f2"] };
// XML 1.0 excludes control characters and unpaired surrogates, even in text nodes.
const xml = value => String(value).replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\ufffe\uffff]|\p{Surrogate}/gu, "�")
  .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&apos;");
// Conservative units keep CJK/emoji labels within their boxes without a canvas or font download.
const units = char => char.codePointAt(0) > 0x2ff || /[WMwm@%]/.test(char) ? 2 : 1;
function shorten(text, budget) {
  const chars = Array.from(String(text));
  if (chars.reduce((sum, char) => sum + units(char), 0) <= budget) return chars.join("");
  let result = "", used = 0;
  for (const char of chars) { if (used + units(char) > budget - 2) break; result += char; used += units(char); }
  return result + "…";
}
function wrapTitle(text, budget, maximum = 3) {
  const chars = Array.from(String(text));
  const lines = []; let start = 0;
  while (start < chars.length && lines.length < maximum) {
    if (lines.length === maximum - 1) {
      lines.push(shorten(chars.slice(start).join(""), budget)); break;
    }
    let end = start, used = 0, space = -1;
    while (end < chars.length && used + units(chars[end]) <= budget) {
      if (/\s/.test(chars[end])) space = end;
      used += units(chars[end]); end++;
    }
    if (end < chars.length && space > start) end = space;
    lines.push(chars.slice(start, end).join("").trimEnd()); start = end;
    while (start < chars.length && /\s/.test(chars[start])) start++;
  }
  return lines;
}

export function modelDiagramSvg(index, { atomKey = null, atomStart = 0, time = 0, quorumIndex = 0, pointStart = 0, width = 800, textScale = 1, propertyName = "" } = {}) {
  if (!index.valid) throw new Error("A valid model scope is needed for a diagram.");
  if (!Number.isInteger(time) || time < 0 || time >= index.scope.stages) throw new Error("Stage outside the model.");
  if (!Number.isInteger(quorumIndex) || !index.quorumMembers[quorumIndex]) throw new Error("Quorum outside the model.");
  if (!Number.isInteger(pointStart) || pointStart < 0 || pointStart >= index.pointNames.length) throw new Error("Participant page outside the model.");
  const atom = atomKey === null ? null : index.atoms.find(item => item.key === atomKey);
  if (atomKey !== null && !atom) throw new Error("Atom outside the model.");
  const overview = atomKey === null && index.atoms.length > 0;
  if (overview && (!Number.isInteger(atomStart) || atomStart < 0 || atomStart >= index.atoms.length)) throw new Error("Atom page outside the model.");
  const shownAtoms = overview ? index.atoms.slice(atomStart, atomStart + ATOMS_PER_PAGE) : atom ? [atom] : [];
  const members = index.quorumMembers[quorumIndex];
  const points = index.pointNames.slice(pointStart, pointStart + POINTS_PER_PAGE);
  const q = `Q${quorumIndex + 1}`;
  // Quote punctuation in names so {a, b} cannot be confused with {"a, b"}.
  const quorumSet = `${q} = {${index.scope.quorums[quorumIndex].map(point => atomLabel(point, [])).join(", ")}}`;
  const otherPageMembers = members.size - points.filter(point => members.has(point)).length;
  const failure = index.failure;
  const failureContext = failure && failure.time === time && failure.quorumIndex === quorumIndex;
  const scale = Number.isFinite(textScale) && textScale > 0 ? textScale : 1;
  const w = Math.max(220, Math.min(1600, Number.isFinite(width) ? Math.round(width / scale) : 800));
  const wide = overview ? (w - 40) / points.length >= 250 : w >= 640;
  const title = `View at stage ${time}`;
  const titleLines = wrapTitle(title, Math.max(16, Math.floor((w - 48) / 10)));
  const propertyLines = propertyName ? wrapTitle(`Property: ${propertyName}`, Math.max(16, Math.floor((w - 48) / 9)), 2) : [];
  const atomLines = atom ? wrapTitle(`Atom: ${atom.label}`, Math.max(16, Math.floor((w - 48) / 9)), 3) : [];
  const stageCoverage = `1 of ${index.scope.stages} ${index.scope.stages === 1 ? "stage" : "stages"} shown`;
  const pointRange = `Participants ${pointStart + 1}–${pointStart + points.length} of ${index.pointNames.length}`;
  const atomRange = overview ? `Atoms ${atomStart + 1}–${atomStart + shownAtoms.length} of ${index.atoms.length}`
    : atom ? `1 of ${index.atoms.length} ${index.atoms.length === 1 ? "atom" : "atoms"} shown` : "No atomic predicates listed";
  const coverageLines = [stageCoverage, pointRange, atomRange]
    .flatMap(line => wrapTitle(line, Math.max(16, Math.floor((w - 48) / 8)), 3));
  const top = 44 + titleLines.length * 23 + (propertyLines.length + atomLines.length) * 21 + coverageLines.length * 20;
  const setBudget = Math.max(16, Math.floor((w - 72) / 9));
  const setLines = wrapTitle(quorumSet, setBudget, 3);
  const setTruncated = wrapTitle(quorumSet, setBudget, 4).length > 3;
  const quorumTitle = wrapTitle(`Highlighted quorum ${q}`, setBudget, 2);
  const quorumCoverage = `1 of ${index.scope.quorums.length} ${index.scope.quorums.length === 1 ? "quorum" : "quorums"} shown`;
  const quorumCoverageLines = wrapTitle(quorumCoverage, Math.max(16, Math.floor((w - 72) / 8)), 3);
  const quorumNote = `${members.size} participant${members.size === 1 ? "" : "s"}${otherPageMembers ? ` · ${otherPageMembers} on other pages` : ""}`;
  const noteLines = wrapTitle(quorumNote, Math.max(16, Math.floor((w - 72) / 8)), 3);
  const continuationLines = setTruncated ? wrapTitle("Full member list in description.", Math.max(16, Math.floor((w - 72) / 8)), 3) : [];
  const qBox = { x: 20, y: top, w: w - 40, h: 24 + quorumTitle.length * 22 + setLines.length * 23 + (quorumCoverageLines.length + noteLines.length + continuationLines.length) * 20 };
  const slotWidth = (w - 40) / points.length;
  const cardWidth = overview
    ? wide ? Math.min(440, slotWidth - 12) : Math.min(440, w - 72)
    : wide ? Math.min(192, slotWidth - 10) : w - 88;
  // Narrow cards put each value below its atom name. This keeps the atom and
  // truth word readable instead of squeezing a two-column row into a phone.
  const stackedAtoms = overview && cardWidth < 300;
  const atomRowHeight = stackedAtoms ? 58 : 36;
  const nodeHeight = overview ? 72 + shownAtoms.length * atomRowHeight : atom ? 142 : 112;
  const gap = 42; // Includes the recorded-failure label beneath a card.
  const firstY = top + qBox.h + 40;
  const cardX = wide ? 0 : overview ? Math.max(48, (w - cardWidth) / 2) : 64;
  const positions = points.map((point, i) => wide
    ? { point, x: 20 + i * slotWidth + (slotWidth - cardWidth) / 2, y: firstY, w: cardWidth }
    : { point, x: cardX, y: firstY + i * (nodeHeight + gap), w: cardWidth });
  const lastBottom = positions.at(-1).y + nodeHeight;
  const h = lastBottom + 60;
  const atomFact = (shownAtom, point) => {
    const v = valueAt(index, shownAtom.key, time, point);
    return `${shownAtom.label}: ${v ? `${v} (${truth[v][0]})` : "value not listed"}`;
  };
  const facts = points.map(point => {
    const v = atom ? valueAt(index, atom.key, time, point) : null;
    const values = overview ? shownAtoms.map(shownAtom => atomFact(shownAtom, point)).join(", ")
      : atom ? (v ? `${v} (${truth[v][0]})` : "value not listed") : "no atomic predicates";
    return `${point}: ${values}; ${members.has(point) ? "member" : "not a member"} of ${q}${failureContext && point === failure.point ? "; recorded property failure here" : ""}.`;
  });
  const boundary = index.scope.time === "stutter" ? "The final stage has itself as its successor." : "The final stage has no successor.";
  const description = `${propertyName ? propertyName + ". " : ""}${title}. This is a selected view, not a whole-model overview. ${atom ? "Selected atom: " + atom.label + ". " : ""}${atomRange}. Stage ${time} of 0–${index.scope.stages - 1}; ${index.scope.time} time. ${stageCoverage}. ${boundary} Highlighted quorum ${quorumSet}. ${quorumCoverage}. A quorum is a set of participants. Lines indicate quorum membership. Selecting another quorum changes membership highlighting, not atomic values. ${otherPageMembers ? `${otherPageMembers} quorum member${otherPageMembers === 1 ? " is" : "s are"} on other participant pages. ` : ""}`
    + `Showing participants ${pointStart + 1}–${pointStart + points.length} of ${index.pointNames.length}. ${facts.join(" ")}`;
  const parts = [`<svg xmlns="http://www.w3.org/2000/svg" width="${w * scale}" height="${h * scale}" viewBox="0 0 ${w} ${h}" role="img" aria-labelledby="diagram-title diagram-description">`,
    `<title id="diagram-title">${xml(propertyName ? propertyName + " · " + title : title)}</title><desc id="diagram-description">${xml(description)}</desc>`,
    '<rect width="100%" height="100%" rx="12" fill="#f5f8fd"/>',
    '<g font-family="system-ui, -apple-system, Segoe UI, sans-serif" fill="#192435">'];
  const text = (x, y, content, attributes = "") => `<text x="${x}" y="${y}" ${attributes}>${xml(content)}</text>`;
  let headerY = 32;
  for (const line of titleLines) { parts.push(text(24, headerY, line, 'font-size="18" font-weight="600"')); headerY += 23; }
  for (const line of [...propertyLines, ...atomLines]) { parts.push(text(24, headerY, line, 'font-size="16" fill="#536278"')); headerY += 21; }
  parts.push('<g data-view-coverage="true">');
  for (const line of coverageLines) { parts.push(text(24, headerY, line, 'font-size="14" fill="#536278"')); headerY += 20; }
  parts.push('</g>');
  for (const [i, p] of positions.entries()) {
    if (!members.has(p.point)) continue;
    const path = wide ? `M ${p.x + p.w / 2} ${top + qBox.h} V ${p.y}`
      : `M 32 ${top + qBox.h} V ${p.y + 30} H ${p.x}`;
    parts.push(`<path data-quorum-edge="${pointStart + i}" d="${path}" fill="none" stroke="#2457d6" stroke-width="2"/>`);
  }
  parts.push(`<g data-quorum-set="${quorumIndex}"><title>${xml(`Highlighted quorum ${quorumSet}. ${quorumCoverage}. ${quorumNote}.`)}</title>`,
    `<rect x="${qBox.x}" y="${qBox.y}" width="${qBox.w}" height="${qBox.h}" rx="9" fill="#2457d6"/>`);
  let quorumY = top + 26;
  for (const line of quorumTitle) { parts.push(text(36, quorumY, line, 'font-size="16" font-weight="600" fill="#ffffff"')); quorumY += 22; }
  for (const line of setLines) { parts.push(text(36, quorumY, line, 'font-size="16" fill="#ffffff"')); quorumY += 23; }
  for (const line of [...quorumCoverageLines, ...noteLines, ...continuationLines]) { parts.push(text(36, quorumY, line, 'font-size="14" fill="#ffffff"')); quorumY += 20; }
  parts.push("</g>");
  function badge(x, y, value, availableWidth, empty = false) {
    const [word, color, background] = truth[value] || [empty ? "no atoms" : "unlisted", "#536278", "#ffffff"];
    const badgeWidth = Math.min(availableWidth, 112);
    parts.push(`<rect x="${x}" y="${y}" width="${badgeWidth}" height="30" rx="6" fill="${background}"/>`,
      text(x + badgeWidth / 2, y + 21, empty ? word : `${value || "?"} ${word}`, `text-anchor="middle" font-size="16" font-weight="600" fill="${color}"`));
  }
  for (const [i, p] of positions.entries()) {
    const marked = !!failureContext && p.point === failure.point;
    parts.push(`<g data-point-index="${pointStart + i}" data-member="${members.has(p.point)}" data-failure="${marked}"><title>${xml(facts[i])}</title>`);
    if (marked) parts.push(`<rect x="${p.x - 4}" y="${p.y - 4}" width="${p.w + 8}" height="${nodeHeight + 8}" rx="13" fill="none" stroke="#805116" stroke-width="2" stroke-dasharray="5 3"/>`);
    parts.push(`<rect x="${p.x}" y="${p.y}" width="${p.w}" height="${nodeHeight}" rx="9" fill="#ffffff" stroke="${members.has(p.point) ? "#2457d6" : "#8594a9"}" stroke-width="1.5"/>`,
      `<rect x="${p.x + 1}" y="${p.y + 1}" width="${p.w - 2}" height="55" rx="8" fill="${members.has(p.point) ? "#eaf0ff" : "#f2f4f7"}"/>`,
      text(p.x + p.w / 2, p.y + 23, shorten(p.point, Math.max(5, Math.floor((p.w - 20) / 9))), 'text-anchor="middle" font-size="16" font-weight="600"'),
      text(p.x + p.w / 2, p.y + 44, shorten(`${members.has(p.point) ? "In" : "Outside"} ${q}`, Math.max(7, Math.floor((p.w - 12) / 8))), `text-anchor="middle" font-size="14" fill="${members.has(p.point) ? "#2457d6" : "#536278"}"`));
    if (overview) {
      shownAtoms.forEach((shownAtom, atomNumber) => {
        const rowY = p.y + 63 + atomNumber * atomRowHeight;
        const v = valueAt(index, shownAtom.key, time, p.point);
        const labelWidth = stackedAtoms ? p.w - 24 : p.w - 150;
        parts.push(`<g data-atom-index="${atomStart + atomNumber}" data-value="${v || "?"}"><title>${xml(atomFact(shownAtom, p.point))}</title>`,
          text(p.x + 12, rowY + 17, shorten(shownAtom.label, Math.max(5, Math.floor(labelWidth / 9))), 'font-size="16"'));
        badge(stackedAtoms ? p.x + 12 : p.x + p.w - 124, stackedAtoms ? rowY + 22 : rowY, v, p.w - 24);
        parts.push("</g>");
      });
    } else {
      const v = atom ? valueAt(index, atom.key, time, p.point) : null;
      if (atom) parts.push(`<g><title>${xml(atom.label)}</title>`,
        text(p.x + p.w / 2, p.y + 77, shorten(atom.label, Math.max(5, Math.floor((p.w - 20) / 9))), 'text-anchor="middle" font-size="16"'), "</g>");
      const badgeWidth = Math.min(p.w - 12, 112);
      badge(p.x + (p.w - badgeWidth) / 2, p.y + (atom ? 92 : 62), v, p.w - 12, !atom);
    }
    if (marked) parts.push(text(p.x + p.w / 2, p.y + nodeHeight + 21, p.w >= 160 ? "Property false here" : "Property false", 'text-anchor="middle" font-size="14" fill="#805116" font-weight="600"'));
    parts.push("</g>");
  }
  parts.push(text(24, h - 20, "Lines: quorum membership", 'font-size="14" fill="#536278"'));
  parts.push("</g></svg>");
  return { svg: parts.join("\n"), description, width: w * scale, height: h * scale };
}
