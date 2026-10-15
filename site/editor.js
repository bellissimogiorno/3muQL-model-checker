/* Colour the source without replacing the browser's native text editor. */
import { highlightSource } from "./highlight.js";

/** Map the parser's one-based Unicode position to a native textarea selection. */
export function sourceSelection(source, line, column = 1) {
  let start = 0, end = source.length, currentLine = 1;
  // The literate loader uses Python splitlines(), including Unicode separators.
  for (const match of source.matchAll(/\r\n|[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]/g)) {
    if (currentLine >= line) { end = match.index; break; }
    start = match.index + match[0].length;
    currentLine++;
  }
  if (currentLine < line) return [source.length, source.length];
  const width = offset => source.codePointAt(offset) > 0xffff ? 2 : 1;
  // JavaScript selection offsets count UTF-16 units; Python counts code points.
  for (let currentColumn = 1; currentColumn < column && start < end; currentColumn++) start += width(start);
  return [start, Math.min(end, start + width(start))];
}

export function createSourceHighlighter({ editor, layer, code, toggle, disclosure }) {
  const frame = editor.parentElement;
  const forcedColors = matchMedia("(forced-colors: active)");
  let composing = false;
  let pending = 0;
  let painted = null;

  function plainText() {
    frame.classList.remove("syntax-highlighted");
    layer.hidden = true;
    code.replaceChildren();
    painted = null;
  }

  function sync() {
    // clientWidth excludes the native scrollbar; both layers then wrap alike.
    layer.style.width = `${editor.clientWidth}px`;
    layer.style.height = `${editor.clientHeight}px`;
    layer.scrollTop = editor.scrollTop;
    layer.scrollLeft = editor.scrollLeft;
  }

  function refresh() {
    if (pending) cancelAnimationFrame(pending);
    pending = 0;
    const source = editor.value;
    if (!toggle.checked || composing || forcedColors.matches || !source || source.length > 250000 || source.includes("\0")) {
      plainText();
      return;
    }
    try {
      if (source !== painted) {
        // highlightSource escapes every input character before adding fixed spans.
        // The extra newline lets the pre scroll to a final blank line like a textarea.
        const markup = highlightSource(source);
        // Avoid building a huge DOM for unusually dense operator sequences.
        if (markup.length > 1000000) { plainText(); return; }
        code.innerHTML = markup + "\n";
        painted = source;
      }
      layer.hidden = false;
      sync();
      frame.classList.add("syntax-highlighted");
    } catch {
      // Decoration must never leave the only editable source invisible.
      plainText();
    }
  }

  function schedule() {
    if (!pending) pending = requestAnimationFrame(refresh);
  }

  editor.addEventListener("input", schedule);
  editor.addEventListener("scroll", sync, { passive: true });
  editor.addEventListener("compositionstart", () => { composing = true; refresh(); });
  editor.addEventListener("compositionend", () => { composing = false; refresh(); });
  toggle.addEventListener("change", refresh);
  disclosure.addEventListener("toggle", refresh);
  forcedColors.addEventListener("change", refresh);
  window.addEventListener("resize", sync, { passive: true });
  // Native drag resizing and responsive layout changes both affect wrapping.
  if (typeof ResizeObserver === "function") {
    const observer = new ResizeObserver(sync);
    observer.observe(editor);
  } else {
    toggle.checked = false;
    toggle.disabled = true;
  }
  refresh();
  return { refresh, sync };
}
