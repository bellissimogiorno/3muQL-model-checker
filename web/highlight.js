/**
 * A small, dependency-free colour layer for the literate source editor.
 *
 * This is deliberately a highlighter, not a second parser or validator. The
 * Python loader still decides whether a theory is valid. Its fence rules and
 * source spellings are mirrored here; strings and comments stay untouched.
 * Every output span contains escaped source text, never interpreted Markdown.
 */

const DECLARATIONS = new Set([
  "theory", "points", "values", "stages", "time", "quorums",
  "predicate", "axiom", "property", "let",
]);
const NAMED_DECLARATIONS = new Set(["predicate", "axiom", "property", "let"]);
const WORD_OPERATORS = new Set(["not", "and", "or", "xor", "forall", "exists", "affine", "unique", "mu", "nu"]);
const BUILTINS = new Set([
  "T", "F", "B", "TB", "TF", "FB", "diamond", "box", "somewhere", "everywhere",
  "existsQ", "forallQ", "quorum", "contra", "someQuorumSomePoint", "everyQuorumEveryPoint",
  "someQuorumEveryPoint", "everyQuorumSomePoint", "yesterday", "tomorrow", "once",
  "historically", "past", "sometime", "forever", "infinitely", "ultimately", "latest", "twined",
  "t", "b", "f",
]);

// Longest spellings come first, matching muql/syntax.py. The rejected => spelling
// has a separate branch so it cannot look like a valid equality operator.
const LOGIC_TOKEN = /(?<space>\s+)|(?<invalid>=>)|(?<operator>[∃∀][Qꟴ][□◇⋄]?|∃⁰¹|∃¹|∃01|∃1|∃!|[¬∧∨⊕→⇀≡≤≠∀∃μµν□◇⋄]|<=>|-\\|->|<=|==|!=|&&|\|\||[!&|^=])|(?<number>[0-9]+)|(?<name>[A-Za-z_][A-Za-z_0-9]*)/y;
const FENCE = /^ {0,3}(`{3,}|~{3,})(.*)$/;
const LINE_ENDINGS = /(\r\n|[\n\r\v\f\x1c-\x1e\x85\u2028\u2029])/;

function escapeHTML(text) {
  return text.replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

function span(kind, text) {
  return text ? `<span class="syntax-${kind}">${escapeHTML(text)}</span>` : "";
}

// Keep uncoloured runs together: even a long line of unknown characters emits
// one escaped text node rather than one span per character.
function lineWriter(text) {
  const chunks = [];
  let plainStart = 0;
  return {
    mark(start, end, kind) {
      chunks.push(escapeHTML(text.slice(plainStart, start)), span(kind, text.slice(start, end)));
      plainStart = end;
    },
    finish() {
      chunks.push(escapeHTML(text.slice(plainStart)));
      return chunks.join("");
    },
  };
}

function highlightLogic(line) {
  const output = lineWriter(line);
  let offset = 0, firstToken = true, expectName = false;
  while (offset < line.length) {
    const character = line[offset];
    if (character === "#" || (character === "/" && line[offset + 1] === "/")) {
      output.mark(offset, line.length, "comment");
      break;
    }
    if (character === '"' || character === "'") {
      let end = offset + 1;
      while (end < line.length) {
        if (line[end] === "\\") end = Math.min(end + 2, line.length);
        else if (line[end++] === character) break;
      }
      output.mark(offset, end, "string");
      offset = end;
      firstToken = false;
      expectName = false;
      continue;
    }
    LOGIC_TOKEN.lastIndex = offset;
    const token = LOGIC_TOKEN.exec(line);
    if (!token) {
      offset++;
      if (!/\s/.test(character)) {
        firstToken = false;
        expectName = false;
      }
      continue;
    }
    const { groups } = token;
    let kind;
    if (groups.space) {
      offset = LOGIC_TOKEN.lastIndex;
      continue;
    }
    if (groups.name) {
      const name = groups.name;
      if (expectName) kind = "name";
      else if (DECLARATIONS.has(name)) kind = "keyword";
      else if (WORD_OPERATORS.has(name)) kind = "operator";
      else if (BUILTINS.has(name)) kind = "builtin";
      expectName = firstToken && NAMED_DECLARATIONS.has(name);
    } else {
      kind = groups.invalid ? "invalid" : groups.operator ? "operator" : "number";
      expectName = false;
    }
    if (kind) output.mark(offset, LOGIC_TOKEN.lastIndex, kind);
    offset = LOGIC_TOKEN.lastIndex;
    firstToken = false;
  }
  return output.finish();
}

function highlightMarkdown(line) {
  if (/^ {0,3}#{1,6}(?:\s|$)/.test(line)) return span("heading", line);

  const output = lineWriter(line);
  // Index backtick runs once. Looking for a matching delimiter at every opening
  // position would otherwise make a line with many unfinished code spans slow.
  const nextRun = new Map(), matchingRun = new Map();
  const runs = [...line.matchAll(/`+/g)];
  for (let index = runs.length - 1; index >= 0; index--) {
    const run = runs[index];
    if (nextRun.has(run[0].length)) matchingRun.set(run.index, nextRun.get(run[0].length));
    nextRun.set(run[0].length, run.index);
  }
  const inlineToken = /(?<code>`+)|(?<link>!?\[[^\[\]]*\]\([^()]*\))|(?<marker>\*\*|__|\*|_)/y;
  const prefix = /^ {0,3}(?:>\s?|[-+*]\s|[0-9]+[.)]\s)/.exec(line);
  let offset = 0;
  if (prefix) {
    output.mark(0, prefix[0].length, "markup");
    offset = prefix[0].length;
  }
  while (offset < line.length) {
    // A backslash keeps an escaped Markdown delimiter literal.
    if (line[offset] === "\\") {
      offset += Math.min(2, line.length - offset);
      continue;
    }
    inlineToken.lastIndex = offset;
    const token = inlineToken.exec(line);
    if (!token) {
      offset++;
      continue;
    }
    let end = inlineToken.lastIndex;
    if (token.groups.code) {
      if (matchingRun.has(offset)) {
        end = matchingRun.get(offset) + token[0].length;
        output.mark(offset, end, "code");
      }
    } else if (token.groups.link) output.mark(offset, end, "link");
    else if (token.groups.marker !== "_" || !(/[A-Za-z0-9]/.test(line[offset - 1] || "") && /[A-Za-z0-9]/.test(line[end] || ""))) {
      output.mark(offset, end, "markup");
    }
    offset = end;
  }
  return output.finish();
}

/** Return escaped, coloured HTML whose text content is exactly source. */
export function highlightSource(source) {
  const lines = source.split(LINE_ENDINGS);
  const output = [];
  let fence = null, executable = false;
  for (let index = 0; index < lines.length; index += 2) {
    const line = lines[index];
    const match = FENCE.exec(line);
    if (fence === null && match) {
      fence = match[1];
      // muql/theory.py requires this exact, case-sensitive info string.
      executable = match[2].trim() === "muql";
      output.push(span("markup", line));
    } else if (fence !== null && match && match[1][0] === fence[0] && match[1].length >= fence.length && match[2].trim() === "") {
      fence = null;
      executable = false;
      output.push(span("markup", line));
    } else output.push(fence !== null ? (executable ? highlightLogic(line) : span("code", line)) : highlightMarkdown(line));
    if (index + 1 < lines.length) output.push(lines[index + 1]);
  }
  return output.join("");
}
