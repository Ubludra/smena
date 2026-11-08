/** Split plain material content into text and clickable URLs. */

export type ContentPart =
  | { kind: "text"; value: string }
  | { kind: "url"; value: string };

const URL_PATTERN = /https?:\/\/[^\s<>"'()[\]{}]+/g;

export function splitContentUrls(content: string): ContentPart[] {
  const parts: ContentPart[] = [];
  let lastIndex = 0;
  for (const match of content.matchAll(URL_PATTERN)) {
    const start = match.index ?? 0;
    if (start > lastIndex) {
      parts.push({ kind: "text", value: content.slice(lastIndex, start) });
    }
    // Trailing punctuation that usually isn't part of the URL.
    let url = match[0];
    url = url.replace(/[.,;:!?]+$/, "");
    parts.push({ kind: "url", value: url });
    lastIndex = start + url.length;
  }
  if (lastIndex < content.length) {
    parts.push({ kind: "text", value: content.slice(lastIndex) });
  }
  return parts;
}
