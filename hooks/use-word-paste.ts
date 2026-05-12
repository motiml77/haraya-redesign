import { useEffect, useCallback, RefObject } from 'react';
import { convertWordHtmlToMarkdown } from '@/lib/word-to-markdown';
import { convertGoogleDocsHtmlToMarkdown } from '@/lib/gdocs-to-markdown';

/**
 * Attaches a paste event handler to a textarea that converts
 * rich HTML clipboard content (Word / Google Docs / any source) to Markdown.
 * Plain-text-only pastes are left untouched.
 */
export function useWordPasteHandler(
  textareaRef: RefObject<HTMLTextAreaElement | null>,
  setValue: (value: string) => void,
  getValue: () => string
): void {
  const handlePaste = useCallback((e: ClipboardEvent) => {
    console.warn('[Paste] event fired! Available types:', e.clipboardData?.types);
    const html = e.clipboardData?.getData('text/html');
    const text = e.clipboardData?.getData('text/plain');

    console.warn('[Paste] html length:', html?.length || 0, '| text length:', text?.length || 0);

    // Only intercept if there is HTML content
    if (!html) {
      console.warn('[Paste] No HTML in clipboard, falling back to default paste');
      return;
    }

    console.warn('[Paste] HTML first 2000 chars:', html.substring(0, 2000));

    // Detect source
    const isWordHtml = /class="?Mso|mso-|<o:p>|<w:|urn:schemas-microsoft-com:office/i.test(html);
    const isGoogleDocsHtml = /docs-internal-guid/i.test(html);

    // For any other HTML source: check if it contains formatting worth converting
    const hasRichFormatting = !isWordHtml && !isGoogleDocsHtml && (
      /font-weight\s*:\s*(bold|[7-9]\d\d)/i.test(html) ||
      /text-decoration\s*:[^;]*underline/i.test(html) ||
      /font-style\s*:\s*italic/i.test(html) ||
      /font-size\s*:/i.test(html) ||
      /<\s*(b|strong|i|em|u)\s*[ >]/i.test(html)
    );

    console.log('[Paste] isWord:', isWordHtml, '| isGDocs:', isGoogleDocsHtml, '| hasRich:', hasRichFormatting);

    if (!isWordHtml && !isGoogleDocsHtml && !hasRichFormatting) return;

    e.preventDefault();

    // Word has its own specialized converter; everything else uses the generic one
    const markdown = isWordHtml
      ? convertWordHtmlToMarkdown(html)
      : convertGoogleDocsHtmlToMarkdown(html);
    const textarea = e.target as HTMLTextAreaElement;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const currentValue = getValue();
    const newValue = currentValue.substring(0, start) + markdown + currentValue.substring(end);

    setValue(newValue);

    // Restore cursor position and trigger resize
    requestAnimationFrame(() => {
      const newPos = start + markdown.length;
      textarea.setSelectionRange(newPos, newPos);
      textarea.style.height = 'auto';
      textarea.style.height = textarea.scrollHeight + 'px';
    });
  }, [getValue, setValue]);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) {
      console.warn('[Paste] hook ran but textarea ref is null — listener NOT attached');
      return;
    }

    console.warn('[Paste] listener ATTACHED to textarea');
    textarea.addEventListener('paste', handlePaste);
    return () => textarea.removeEventListener('paste', handlePaste);
  }, [textareaRef, handlePaste]);
}
