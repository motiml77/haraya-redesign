'use client';

import React from 'react';
import Markdown from 'react-markdown';
import rehypeRaw from 'rehype-raw';

// --- Footnote Processing ---
// Extracts [^N]: definitions and converts [^N] markers to HTML
interface FootnoteData {
  id: string;
  num: number;
  text: string;
}

export function processFootnotes(text: string): { processedText: string; footnotes: FootnoteData[] } {
  if (!text) return { processedText: text, footnotes: [] };

  // Extract footnote definitions: [^N]: text (at end of document, or anywhere)
  // Also match empty definitions [^N]: (no text) — these come from Word paste when content is missing
  const footnotes: FootnoteData[] = [];
  const defRegex = /^\[\^(\d+)\]:\s*(.*)$/gm;
  let match;
  while ((match = defRegex.exec(text)) !== null) {
    const fnText = match[2].trim() || '(הערה חסרה — יש להוסיף ידנית)';
    footnotes.push({ id: `fn-${match[1]}`, num: parseInt(match[1]), text: fnText });
  }

  if (footnotes.length === 0) return { processedText: text, footnotes: [] };

  // Remove definition lines from the text
  let processedText = text.replace(/^\[\^(\d+)\]:\s*.*$/gm, '').trim();

  // Sort footnotes by number
  footnotes.sort((a, b) => a.num - b.num);

  // Renumber footnotes sequentially from 1
  const numMap = new Map<number, number>();
  footnotes.forEach((fn, i) => {
    numMap.set(fn.num, i + 1);
    fn.num = i + 1;
    fn.id = `fn-${i + 1}`;
  });

  // Replace [^N] markers in text with superscript HTML
  processedText = processedText.replace(/\[\^(\d+)\]/g, (_, num) => {
    const newNum = numMap.get(parseInt(num));
    if (newNum === undefined) return `[^${num}]`; // Unknown reference, leave as-is
    return `<sup class="footnote-ref"><a href="#fn-${newNum}" id="fnref-${newNum}">${newNum}</a></sup>`;
  });

  return { processedText, footnotes };
}

// --- Footnote Section Component ---
function FootnoteSection({ footnotes }: { footnotes: FootnoteData[] }) {
  if (footnotes.length === 0) return null;
  return (
    <div className="mt-8 pt-4 border-t border-[#E5E0D8]" dir="rtl">
      <h4 className="text-sm font-bold text-[#8C7A6B] mb-3">הערות</h4>
      <ol className="list-none space-y-2 text-sm text-[#4A3B32]">
        {footnotes.map(fn => (
          <li key={fn.id} id={fn.id} className="flex gap-2 leading-relaxed">
            <span className="font-bold text-[#8C2B2B] shrink-0">{fn.num}.</span>
            <span className="flex-1">{fn.text}
              <a href={`#fnref-${fn.num}`} className="text-[#8C7A6B] hover:text-[#8C2B2B] mr-1 no-underline" title="חזרה לטקסט">↩</a>
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

// --- Tooltip Processing (unchanged) ---
// Convert [word](tooltip:explanation) to HTML spans BEFORE react-markdown
// Uses a parser to handle parentheses within tooltip text
export const processTooltipMarkdown = (text: string) => {
  if (!text) return text;
  let result = text;

  // Fix broken tooltips where link text is an HTML tag - use preceding word
  result = result.replace(/([\p{L}\p{N}]+)\s*\[<[^>]*>\]\(tooltip:([^)]*)\)/gu, (_, word, tooltip) => {
    return `[${word}](tooltip:${tooltip})`;
  });

  // Find and convert all [word](tooltip:...) patterns
  // Handle nested parentheses by counting open/close parens
  let output = '';
  let i = 0;
  while (i < result.length) {
    // Look for [
    const bracketStart = result.indexOf('[', i);
    if (bracketStart === -1) { output += result.slice(i); break; }

    output += result.slice(i, bracketStart);

    // Find matching ]
    const bracketEnd = result.indexOf(']', bracketStart + 1);
    if (bracketEnd === -1) { output += result.slice(bracketStart); break; }

    const word = result.slice(bracketStart + 1, bracketEnd);

    // Check for (tooltip: right after ] (allow optional whitespace for Word-pasted content)
    const afterBracket = result.substring(bracketEnd + 1, bracketEnd + 20);
    const tooltipPrefix = afterBracket.match(/^\s*\(tooltip:/);
    if (tooltipPrefix) {
      const tooltipStart = bracketEnd + 1 + tooltipPrefix[0].length;
      // Detect if content is URL-encoded (old data used encodeURIComponent)
      const isUrlEncoded = /^%[0-9A-Fa-f]{2}/.test(result.substring(tooltipStart, tooltipStart + 3));

      let j: number;
      if (isUrlEncoded) {
        // For URL-encoded content: encodeURIComponent doesn't encode ( and )
        // so depth counting fails. Instead, find the last ) before the next [ or newline.
        let searchEnd = result.length;
        const nextNewline = result.indexOf('\n', tooltipStart);
        if (nextNewline !== -1 && nextNewline < searchEnd) searchEnd = nextNewline;
        const nextBracket = result.indexOf('[', tooltipStart);
        if (nextBracket !== -1 && nextBracket < searchEnd) searchEnd = nextBracket;
        j = -1;
        for (let k = searchEnd - 1; k >= tooltipStart; k--) {
          if (result[k] === ')') { j = k; break; }
        }
        if (j === -1) { output += '['; i = bracketStart + 1; continue; }
      } else {
        // Plain text: use depth counting for balanced parens
        let depth = 1;
        j = tooltipStart;
        while (j < result.length && depth > 0) {
          if (result[j] === '(') depth++;
          else if (result[j] === ')') depth--;
          if (depth > 0) j++;
        }
        if (depth !== 0) { output += '['; i = bracketStart + 1; continue; }
      }

      const tooltipRaw = result.slice(tooltipStart, j);
      const cleanWord = word.replace(/<[^>]*>/g, '').trim();

      if (cleanWord) {
        let explanation: string;
        try { explanation = decodeURIComponent(tooltipRaw); } catch { explanation = tooltipRaw; }

        const escaped = explanation
          .replace(/&/g, '&amp;')
          .replace(/"/g, '&quot;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;');

        output += `<span class="tooltip-word" data-tooltip="${escaped}">${cleanWord}</span>`;
        i = j + 1; // skip past closing )
        continue;
      }
    }

    // Not a tooltip - output the [ and continue
    output += '[';
    i = bracketStart + 1;
  }

  return output;
};

// --- Tooltip Component ---
function TooltipSpan({ explanation, children }: { explanation: string; children: React.ReactNode }) {
  return (
    <span className="relative group inline-block cursor-help border-b-2 border-dotted border-[#8C2B2B] text-[#8C2B2B] font-bold mx-1">
      {children}
      <span className="absolute bottom-full right-1/2 translate-x-1/2 mb-2 hidden group-hover:block bg-[#4A3B32] text-white text-sm p-3 rounded-xl shadow-xl w-max max-w-[250px] z-50 text-center font-sans font-normal leading-relaxed pointer-events-none">
        {explanation}
        <span className="absolute top-full right-1/2 translate-x-1/2 border-4 border-transparent border-t-[#4A3B32]"></span>
      </span>
    </span>
  );
}

// --- Custom Markdown Components ---
function makeComponents(pClassName: string) {
  return {
    a: ({ node, href, children, ...props }: any) => {
      if (href?.startsWith('tooltip:')) {
        let explanation: string;
        try { explanation = decodeURIComponent(href.replace('tooltip:', '')); } catch { explanation = href.replace('tooltip:', ''); }
        return <TooltipSpan explanation={explanation}>{children}</TooltipSpan>;
      }
      // Footnote reference links — style as superscript
      if (href?.startsWith('#fn-')) {
        return <a href={href} {...props} className="text-[#8C2B2B] hover:underline font-bold no-underline">{children}</a>;
      }
      // Footnote back-links
      if (href?.startsWith('#fnref-')) {
        return <a href={href} {...props} className="text-[#8C7A6B] hover:text-[#8C2B2B] no-underline mr-1">{children}</a>;
      }
      return <a href={href} {...props} target="_blank" rel="noopener noreferrer" className="text-[#8C2B2B] hover:underline font-bold">{children}</a>;
    },
    span: ({ node, className, ...props }: any) => {
      if (className === 'tooltip-word') {
        // rehypeRaw converts data-tooltip to dataTooltip (camelCase)
        const explanation = props.dataTooltip || props['data-tooltip'] || '';
        const { dataTooltip: _a, 'data-tooltip': _b, ...rest } = props;
        return <TooltipSpan explanation={explanation}><span {...rest} /></TooltipSpan>;
      }
      if (className === 'citation-font') {
        return <span className="font-['FrankRuehl',_'Miriam',_'Times_New_Roman',_serif] text-[#1a5276] border-b border-dotted border-[#1a5276]/30" {...props} />;
      }
      return <span className={className} {...props} />;
    },
    sup: ({ node, className, ...props }: any) => {
      if (className === 'footnote-ref') {
        return <sup className="text-[10px] text-[#8C2B2B] font-bold cursor-pointer mx-0.5" {...props} />;
      }
      return <sup className={className} {...props} />;
    },
    p: ({ node, ...props }: any) => <p {...props} className={pClassName} />,
    h2: ({ node, ...props }: any) => <h2 {...props} className="text-xl font-serif font-bold text-[#4A3B32] mt-8 mb-3 pb-2 border-b border-[#E5E0D8]" />,
    h3: ({ node, ...props }: any) => <h3 {...props} className="text-lg font-serif font-bold text-[#4A3B32] mt-6 mb-2" />,
    h4: ({ node, ...props }: any) => <h4 {...props} className="text-base font-bold text-[#4A3B32] mt-4 mb-2" />,
  };
}

// --- Main Components ---
export function MarkdownRenderer({ children, className }: { children: string; className?: string }) {
  // Process footnotes first, then tooltips
  const { processedText, footnotes } = processFootnotes(children);

  return (
    <>
      <Markdown
        rehypePlugins={[rehypeRaw]}
        urlTransform={(value: string) => value}
        components={makeComponents(className || "inline")}
      >
        {processTooltipMarkdown(processedText)}
      </Markdown>
      <FootnoteSection footnotes={footnotes} />
    </>
  );
}

export function SimpleMarkdown({ children }: { children: string }) {
  const { processedText, footnotes } = processFootnotes(children);

  return (
    <>
      <Markdown
        rehypePlugins={[rehypeRaw]}
        urlTransform={(value: string) => value}
        components={makeComponents("mb-2 last:mb-0")}
      >
        {processTooltipMarkdown(processedText)}
      </Markdown>
      <FootnoteSection footnotes={footnotes} />
    </>
  );
}
