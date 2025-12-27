import DOMPurify from 'dompurify';

const ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'u', 's', 'ol', 'ul', 'li', 'a', 'hr'];
const ALLOWED_ATTR: Record<string, string[]> = { a: ['href', 'target', 'rel'] };

const HTML_TAG_RE = /<\/?(p|br|strong|em|u|s|ol|ul|li|a|hr)\b/i;

const escapeHtml = (text: string) =>
  text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

const markdownToHtml = (text: string) => {
  const normalized = (text || '').replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  let escaped = escapeHtml(normalized);
  escaped = escaped.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  escaped = escaped.replace(/\*([^*]+)\*/g, '<em>$1</em>');
  escaped = escaped.replace(/_([^_]+)_/g, '<em>$1</em>');
  const paragraphs = escaped.split(/\n{2,}/).map((paragraph) => paragraph.trim()).filter(Boolean);
  if (!paragraphs.length) {
    return escaped.replace(/\n/g, '<br>');
  }
  return paragraphs
    .map((paragraph) => `<p>${paragraph.replace(/\n/g, '<br>')}</p>`)
    .join('\n');
};

export const isHtmlContent = (text: string) => HTML_TAG_RE.test(text || '');

export const toSafeHtml = (text: string) => {
  const html = isHtmlContent(text) ? text : markdownToHtml(text);
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
  });
};

export const htmlToText = (text: string) => {
  if (typeof window === 'undefined') {
    return text;
  }
  const doc = new DOMParser().parseFromString(text, 'text/html');
  return doc.body.textContent || '';
};

export const normalizeToHtml = (text: string) => {
  const html = isHtmlContent(text) ? text : markdownToHtml(text);
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
  });
};
