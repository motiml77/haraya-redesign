import { useEffect, useCallback, RefObject } from 'react';
import { convertWordHtmlToMarkdown } from '@/lib/word-to-markdown';

/**
 * Attaches a paste event handler to a textarea that converts
 * Word HTML clipboard content to Markdown before inserting.
 * Non-Word pastes are left untouched.
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

    // Check if the HTML is from Word
    const isWordHtml = /class="?Mso|mso-|<o:p>|<w:|urn:schemas-microsoft-com:office/i.test(html);
    if (!isWordHtml) return;

    e.preventDefault();

    const markdown = convertWordHtmlToMarkdown(html);
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
