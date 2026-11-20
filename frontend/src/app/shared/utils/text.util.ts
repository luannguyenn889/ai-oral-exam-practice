const HTML_TAG_CHECK_RE = /<\/?[a-zA-Z][a-zA-Z0-9:-]*(?:\s+[^>]*)?\/?>/;
const HTML_LI_OPEN_RE = /<li\b[^>]*>/gi;
const HTML_LI_CLOSE_RE = /<\/li>/gi;
const HTML_BLOCK_BREAK_RE =
  /<\/?(?:ul|ol|p|div|section|article|blockquote|tr|h[1-6])\b[^>]*>|<br\s*\/?>/gi;
const HTML_TD_CLOSE_RE = /<\/t[dh]\s*>/gi;

/**
 * Chuyển chuỗi chứa thẻ HTML (<ul>, <li>, <p>, <br>...) sang văn bản thuần có xuống dòng gạch đầu dòng.
 */
export function cleanHtmlToPlainText(raw?: string | null): string {
  if (!raw) return '';
  let text = raw
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/\u00a0/g, ' ')
    .replace(/\r\n/g, '\n')
    .replace(/\r/g, '\n');

  if (HTML_TAG_CHECK_RE.test(text)) {
    text = text
      .replace(HTML_LI_OPEN_RE, '\n- ')
      .replace(HTML_LI_CLOSE_RE, '\n')
      .replace(HTML_BLOCK_BREAK_RE, '\n')
      .replace(HTML_TD_CLOSE_RE, ' ')
      .replace(new RegExp(HTML_TAG_CHECK_RE.source, 'g'), '')
      .replace(/\n{2,}/g, '\n');
  }

  const lines: string[] = [];
  let prevBlank = false;
  for (const rawLine of text.split('\n')) {
    let line = rawLine.replace(/[ \t]{2,}/g, ' ').trim();
    line = line.replace(/^-\s*[-•●◦▪➢➤►]+\s*/, '- ');
    if (line === '-') continue;
    if (!line) {
      if (lines.length > 0 && !prevBlank) {
        lines.push('');
        prevBlank = true;
      }
      continue;
    }
    lines.push(line);
    prevBlank = false;
  }

  return lines.join('\n').trim();
}
