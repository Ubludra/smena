/**
 * Minimal, dependency-free Markdown renderer for the report editor preview.
 *
 * Security model (the output is mounted via dangerouslySetInnerHTML, so it
 * must be provably inert):
 *
 * 1. every input character goes through escapeHtml FIRST — raw HTML in the
 *    source can never survive into the output (no <script>, no <img onerror>);
 * 2. only the constructs implemented below re-introduce markup;
 * 3. link URLs are allowlisted by scheme (http/https/mailto/#/relative);
 *    anything else (javascript:, data:) is rendered as plain label text.
 *
 * Supported: # .. ###### headings, fenced code blocks, inline `code`,
 * **bold**, *italic*, [label](url), unordered/ordered lists (single level),
 * > blockquotes, pipe tables, --- hr, paragraphs with soft line breaks.
 */

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** Scheme allowlist: everything else loses the link, keeps the label. */
function safeHref(escapedUrl: string): string | null {
  return /^(https?:|mailto:|#|\/)/i.test(escapedUrl) ? escapedUrl : null;
}

function renderInline(text: string): string {
  let s = escapeHtml(text);
  // Code spans are lifted out first (placeholder tokens) so emphasis and
  // link syntax inside them stays literal, then restored untouched.
  // Private-use-area delimiters: not produced by typing, not control chars.
  const codeSpans: string[] = [];
  s = s.replace(/`([^`]+)`/g, (_match, body: string) => {
    codeSpans.push(`<code>${body}</code>`);
    return `\uE000${codeSpans.length - 1}\uE001`;
  });
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  s = s.replace(
    /\[([^\]]+)\]\(([^)\s]+)\)/g,
    (match, label: string, url: string) => {
      const href = safeHref(url);
      return href === null
        ? match
        : `<a href="${href}" target="_blank" rel="noopener noreferrer">${label}</a>`;
    },
  );
  // Out-of-range tokens (if the source itself contained the delimiter pair)
  // resolve to the empty string — never to undefined markup.
  return s.replace(/\uE000(\d+)\uE001/g, (_match, index: string) => {
    const span = codeSpans[Number(index)];
    return span === undefined ? "" : span;
  });
}

export function renderMarkdown(source: string): string {
  const lines = source.replace(/\r\n?/g, "\n").split("\n");
  const out: string[] = [];
  let paragraph: string[] = [];
  let i = 0;

  const flushParagraph = (): void => {
    if (paragraph.length > 0) {
      out.push(`<p>${paragraph.map(renderInline).join("<br>")}</p>`);
      paragraph = [];
    }
  };

  while (i < lines.length) {
    const line = lines[i];

    if (/^\s*```/.test(line)) {
      flushParagraph();
      const buf: string[] = [];
      i += 1;
      while (i < lines.length && !/^\s*```/.test(lines[i])) {
        buf.push(lines[i]);
        i += 1;
      }
      i += 1; // closing fence (absent fence = tolerate, take what is there)
      out.push(`<pre><code>${escapeHtml(buf.join("\n"))}</code></pre>`);
      continue;
    }

    const heading = /^(#{1,6})\s+(.*)$/.exec(line);
    if (heading !== null) {
      flushParagraph();
      const level = heading[1].length;
      out.push(`<h${level}>${renderInline(heading[2])}</h${level}>`);
      i += 1;
      continue;
    }

    if (/^\s*(-{3,}|\*{3,})\s*$/.test(line)) {
      flushParagraph();
      out.push("<hr>");
      i += 1;
      continue;
    }

    if (/^\s*>\s?/.test(line)) {
      flushParagraph();
      const buf: string[] = [];
      while (i < lines.length && /^\s*>\s?/.test(lines[i])) {
        buf.push(lines[i].replace(/^\s*>\s?/, ""));
        i += 1;
      }
      out.push(`<blockquote>${buf.map(renderInline).join("<br>")}</blockquote>`);
      continue;
    }

    // Pipe table: header row + |---| separator + body rows.
    if (
      line.includes("|") &&
      i + 1 < lines.length &&
      lines[i + 1].includes("-") &&
      /^\s*\|?[\s:|-]+\|[\s:|-]*$/.test(lines[i + 1])
    ) {
      flushParagraph();
      const cells = (row: string): string[] =>
        row
          .trim()
          .replace(/^\|/, "")
          .replace(/\|$/, "")
          .split("|")
          .map((c) => renderInline(c.trim()));
      const head = cells(line);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && lines[i].includes("|") && lines[i].trim() !== "") {
        rows.push(cells(lines[i]));
        i += 1;
      }
      out.push(
        `<table><thead><tr>${head.map((c) => `<th>${c}</th>`).join("")}</tr></thead>` +
          `<tbody>${rows
            .map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`)
            .join("")}</tbody></table>`,
      );
      continue;
    }

    if (/^\s*[-*+]\s+/.test(line)) {
      flushParagraph();
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*+]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*+]\s+/, ""));
        i += 1;
      }
      out.push(`<ul>${items.map((t) => `<li>${renderInline(t)}</li>`).join("")}</ul>`);
      continue;
    }

    if (/^\s*\d+[.)]\s+/.test(line)) {
      flushParagraph();
      const items: string[] = [];
      while (i < lines.length && /^\s*\d+[.)]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*\d+[.)]\s+/, ""));
        i += 1;
      }
      out.push(`<ol>${items.map((t) => `<li>${renderInline(t)}</li>`).join("")}</ol>`);
      continue;
    }

    if (line.trim() === "") {
      flushParagraph();
      i += 1;
      continue;
    }

    paragraph.push(line);
    i += 1;
  }
  flushParagraph();
  return out.join("\n");
}

export interface DocumentStats {
  words: number;
  characters: number;
}

export function documentStats(content: string): DocumentStats {
  const trimmed = content.trim();
  return {
    words: trimmed === "" ? 0 : trimmed.split(/\s+/).length,
    characters: content.length,
  };
}
