import { useEffect, useCallback, RefObject } from 'react';
import { convertWordHtmlToMarkdown } from '@/lib/word-to-markdown';
import { convertGoogleDocsHtmlToMarkdown } from '@/lib/gdocs-to-markdown';

/**
 * Attaches a paste event handler to a textarea that converts
 * rich HTML clipboard content (Word / Google Docs) to Markdown before inserting.
 * Plain-text-only pastes are left untouched.
 */
export function useWordPasteHandler(
  textareaRef: RefObject<HTMLTextAreaElement | null>,
  setValue: (value: string) => void,
  getValue: () => string
): void {
  const handlePaste = useCallback((e: ClipboardEvent) => {
    const html = e.clipboardData?.getData('text/html');

    // Only intercept if there is HTML content
    if (!html) return;

    // Detect source
    const isWordHtml = /class="?Mso|mso-|<o:p>|<w:|urn:schemas-microsoft-com:office/i.test(html);
    const isGoogleDocsHtml = /docs-internal-guid|id="docs-internal-guid/i.test(html);

    if (!isWordHtml && !isGoogleDocsHtml) return;

    e.preventDefault();

    const markdown = isGoogleDocsHtml
      ? convertGoogleDocsHtmlToMarkdown(html)
      : convertWordHtmlToMarkdown(html);
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
    if (!textarea) return;

    textarea.addEventListener('paste', handlePaste);
    return () => textarea.removeEventListener('paste', handlePaste);
  }, [textareaRef, handlePaste]);
}
