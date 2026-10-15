/** Typeset quorum quantifiers without changing their copyable source text. */
export function formulaHTML(text) {
  const escape = value => value.replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
  const parts = [];
  let end = 0;
  // Quoted values and comments are literal text, even when they contain ∃Q.
  // Include unfinished quotes defensively; rendering never validates syntax.
  const tokens = /"(?:\\[\s\S]|[^"\\])*(?:"|\\?$)|'(?:\\[\s\S]|[^'\\])*(?:'|\\?$)|#[^\r\n]*|\/\/[^\r\n]*|[∃∀][Qꟴ]/g;
  for (const match of text.matchAll(tokens)) {
    parts.push(escape(text.slice(end, match.index)));
    parts.push(/^[∃∀][Qꟴ]$/.test(match[0])
      ? `<span class="quorum-quantifier">${match[0][0]}${match[0][1] === "Q" ? '<sup class="quorum-mark">Q</sup>' : "ꟴ"}</span>`
      : escape(match[0]));
    end = match.index + match[0].length;
  }
  parts.push(escape(text.slice(end)));
  return parts.join("");
}
