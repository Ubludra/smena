import { describe, expect, it } from "vitest";
import { documentStats, renderMarkdown } from "./markdown";

describe("renderMarkdown blocks", () => {
  it("renders headings by level", () => {
    expect(renderMarkdown("# Раздел")).toContain("<h1>Раздел</h1>");
    expect(renderMarkdown("### Подраздел")).toContain("<h3>Подраздел</h3>");
  });

  it("renders unordered and ordered lists", () => {
    const html = renderMarkdown("- пункт а\n- пункт б");
    expect(html).toBe("<ul><li>пункт а</li><li>пункт б</li></ul>");
    expect(renderMarkdown("1. первый\n2. второй")).toContain(
      "<ol><li>первый</li><li>второй</li></ol>",
    );
  });

  it("renders blockquote, hr and fenced code", () => {
    expect(renderMarkdown("> вывод")).toContain("<blockquote>вывод</blockquote>");
    expect(renderMarkdown("---")).toBe("<hr>");
    expect(renderMarkdown("```\nкод <x>\n```")).toContain(
      "<pre><code>код &lt;x&gt;</code></pre>",
    );
  });

  it("renders a pipe table with header and body", () => {
    const html = renderMarkdown(
      "| Ученик | Балл |\n| --- | --- |\n| Петя | 5 |\n| Маша | 4 |",
    );
    expect(html).toContain("<th>Ученик</th>");
    expect(html).toContain("<td>Петя</td>");
    expect(html).toContain("<td>4</td>");
  });

  it("joins paragraph lines with soft breaks", () => {
    expect(renderMarkdown("строка одна\nстрока две")).toBe(
      "<p>строка одна<br>строка две</p>",
    );
  });
});

describe("renderMarkdown inline", () => {
  it("renders emphasis and code spans", () => {
    expect(renderMarkdown("**жирно**")).toBe("<p><strong>жирно</strong></p>");
    expect(renderMarkdown("*курсив*")).toBe("<p><em>курсив</em></p>");
    expect(renderMarkdown("`код`")).toBe("<p><code>код</code></p>");
  });

  it("keeps emphasis markers inside code literal", () => {
    expect(renderMarkdown("`**не жирно**`")).toBe(
      "<p><code>**не жирно**</code></p>",
    );
  });
});

describe("renderMarkdown safety", () => {
  it("escapes raw HTML instead of passing it through", () => {
    const html = renderMarkdown("<script>alert(1)</script>");
    expect(html).not.toContain("<script>");
    expect(html).toContain("&lt;script&gt;");
  });

  it("escapes attribute-breaking quotes in raw source", () => {
    const html = renderMarkdown('<img src=x onerror="alert(1)">');
    expect(html).not.toContain("<img");
    expect(html).toContain("&quot;");
  });

  it("rejects javascript: and data: link schemes, keeps the label", () => {
    const js = renderMarkdown("[клик](javascript:alert(1))");
    expect(js).not.toContain("href");
    expect(js).toContain("клик");
    const data = renderMarkdown("[тык](data:text/html,abc)");
    expect(data).not.toContain("href");
  });

  it("allows http, https, mailto and anchor links", () => {
    expect(renderMarkdown("[сайт](https://example.com)")).toContain(
      'href="https://example.com"',
    );
    expect(renderMarkdown("[я](mailto:a@b.c)")).toContain('href="mailto:a@b.c"');
    expect(renderMarkdown("[раздел](#otchet)")).toContain('href="#otchet"');
  });

  it("links carry rel=noopener for target=_blank", () => {
    const html = renderMarkdown("[сайт](https://example.com)");
    expect(html).toContain('rel="noopener noreferrer"');
  });
});

describe("documentStats", () => {
  it("counts words and characters", () => {
    expect(documentStats("два   слова тут")).toEqual({
      words: 3,
      characters: 15,
    });
    expect(documentStats("   ")).toEqual({ words: 0, characters: 3 });
    expect(documentStats("")).toEqual({ words: 0, characters: 0 });
  });
});
