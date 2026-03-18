/**
 * Converts Word-pasted HTML to Markdown.
 * Handles bold, underline, italic, small text, line breaks, lists, and footnotes.
 * Word footnotes are converted to [^N] markers + [^N]: definitions at the end.
 * Tooltips ([word](tooltip:text)) are separate and handled by bracket annotations [=...].
 */
export function convertWordHtmlToMarkdown(html: string): string {
  // Step 1: Clean Word-specific junk
  let cleaned = html;

  // Remove conditional comments
  cleaned = cleaned.replace(/<!--\[if[\s\S]*?<!\[endif\]-->/gi, '');
  cleaned = cleaned.replace(/<!--[\s\S]*?-->/g, '');

  // Remove <style>...</style> blocks
  cleaned = cleaned.replace(/<style[\s\S]*?<\/style>/gi, '');

  // Remove <meta>, <link>, <xml>, <o:*>, <w:*> tags
  cleaned = cleaned.replace(/<\/?(?:meta|link|xml|o:\w+|w:\w+|v:\w+|st\d:\w+)[^>]*>/gi, '');

  // Preserve Word heading classes as data attributes, then strip all classes
  cleaned = cleaned.replace(/\s*class="([^"]*)"/gi, (_match, classes) => {
    const headingMatch = classes.match(/MsoHeading(\d)/i);
    if (headingMatch) return ` data-word-heading="${headingMatch[1]}"`;
    return '';
  });

  // Step 2: Parse with DOMParser
  const parser = new DOMParser();
  const doc = parser.parseFromString(cleaned, 'text/html');

  // Step 3: Extract footnotes/endnotes before walking
  const footnotes = extractFootnotes(doc);

  // Step 4: Detect baseline font size and font family
  const baselineSize = detectBaselineFontSize(doc.body);
  const baselineFont = detectBaselineFont(doc.body);

  // Debug: log detection results (remove after debugging)
  console.log('[Word→MD] baselineFont:', baselineFont, '| baselineSize:', baselineSize);
  console.log('[Word→MD] raw HTML (first 2000 chars):', cleaned.substring(0, 2000));

  // Step 5: Walk DOM tree and build Markdown
  // Track used footnotes with renumbering (Word may have non-sequential numbers)
  const footnoteRenumber: FootnoteRenumber = { counter: 0, mapping: new Map(), used: new Map() };
  const markdown = walkNode(doc.body, baselineSize, baselineFont, { listDepth: 0 }, footnotes, footnoteRenumber);

  // Step 6: Post-processing cleanup + append footnote definitions
  return cleanMarkdown(markdown, footnoteRenumber.used);
}

interface FootnoteRenumber {
  counter: number;                     // Next footnote number to assign
  mapping: Map<string, number>;        // Word number → new number
  used: Map<number, string>;           // new number → footnote text
}

/**
 * Cleans footnote text by removing leading number prefixes in all common formats.
 * Handles: "1 ", "[1] ", "(1) ", "1. ", "1) ", etc.
 */
function cleanFootnotePrefix(text: string): string {
  return text.replace(/^[\[\(]?\d+[\]\)]?[.):]?\s*/, '').trim();
}

/**
 * Extracts clean text from a footnote container by cloning the element,
 * removing the footnote number/reference elements (anchors, sups),
 * and collecting the remaining text content.
 * This avoids the issue of textContent mixing number with content.
 */
function getFootnoteContent(el: Element): string {
  const clone = el.cloneNode(true) as HTMLElement;
  // Remove footnote reference anchors (contain the number like [1])
  clone.querySelectorAll('a').forEach(a => {
    const name = a.getAttribute('name') || a.getAttribute('href') || '';
    if (/(?:ftn|edn)/i.test(name)) a.remove();
  });
  // Remove standalone sup elements at the start (footnote numbers)
  clone.querySelectorAll('sup').forEach(sup => {
    const text = sup.textContent?.trim() || '';
    if (/^[\[\(]?\d+[\]\)]?$/.test(text)) sup.remove();
  });
  // Get remaining text, collapse whitespace
  let text = clone.textContent?.replace(/\s+/g, ' ').trim() || '';
  // Still clean any remaining leading number prefix
  text = cleanFootnotePrefix(text);
  return text;
}

/**
 * Extracts Word footnotes and endnotes into a map.
 * Word uses: <a href="#_ftn1"> for references, <div id="ftn1"> for content.
 * Also handles: _edn (endnotes) prefix.
 *
 * Strategies (in priority order):
 * 1. Find containers by ID (ftn1, _ftn1, edn1, etc.)
 * 2. Find containers by mso-element:footnote style
 * 3. Find via anchor name/id attributes
 * 4. Extract from title attributes of reference links
 * 5. Fallback: scan bottom paragraphs with small font
 */
function extractFootnotes(doc: Document): Map<string, string> {
  const footnotes = new Map<string, string>();

  // Mark the footnote-list container so it's skipped during walk
  const fnListContainers = doc.querySelectorAll('[style*="mso-element"]');
  fnListContainers.forEach(el => {
    const style = el.getAttribute('style') || '';
    if (/mso-element\s*:\s*footnote-list/i.test(style)) {
      el.setAttribute('data-footnote-extracted', 'true');
    }
  });

  // Strategy 1: Find footnote containers by ID (ftn1, _ftn1, edn1, etc.)
  const allElements = doc.querySelectorAll('[id]');
  allElements.forEach(el => {
    const id = el.getAttribute('id') || '';
    const match = id.match(/^_?(?:ftn|edn)(\d+)$/i);
    if (match) {
      const num = match[1];
      const text = getFootnoteContent(el);
      if (text) {
        footnotes.set(num, text);
      }
      el.setAttribute('data-footnote-extracted', 'true');
    }
  });

  // Strategy 2: Find footnotes via mso-element:footnote in style attribute
  if (footnotes.size === 0) {
    const styledEls = doc.querySelectorAll('div[style], p[style], section[style]');
    styledEls.forEach(el => {
      const style = el.getAttribute('style') || '';
      if (!/mso-element\s*:\s*footnote\b/i.test(style)) return;
      const id = el.getAttribute('id') || '';
      const idMatch = id.match(/(?:ftn|edn)(\d+)/i);
      if (idMatch) {
        const num = idMatch[1];
        const text = getFootnoteContent(el);
        if (text && !footnotes.has(num)) {
          footnotes.set(num, text);
        }
        el.setAttribute('data-footnote-extracted', 'true');
      }
    });
  }

  // Strategy 3: Find footnotes via anchor name/id attributes (definition anchors)
  if (footnotes.size === 0) {
    const anchors = doc.querySelectorAll('a[name], a[id]');
    anchors.forEach(anchor => {
      const name = anchor.getAttribute('name') || anchor.getAttribute('id') || '';
      // Only match definition anchors (_ftn1), not reference anchors (_ftnref1)
      const match = name.match(/^_?(?:ftn|edn)(\d+)$/i);
      if (match && !footnotes.has(match[1])) {
        const parent = anchor.closest('p, div');
        if (parent) {
          const text = getFootnoteContent(parent);
          if (text) {
            footnotes.set(match[1], text);
            parent.setAttribute('data-footnote-extracted', 'true');
          }
        }
      }
    });
  }

  // Strategy 4: Extract from title attributes of footnote reference links
  if (footnotes.size === 0) {
    const refLinks = doc.querySelectorAll('a[href*="ftn"], a[href*="edn"]');
    refLinks.forEach(link => {
      const href = link.getAttribute('href') || '';
      const match = href.match(/#_?(?:ftn|edn)(\d+)/i);
      if (match) {
        const title = link.getAttribute('title')?.trim();
        if (title && !footnotes.has(match[1])) {
          footnotes.set(match[1], cleanFootnotePrefix(title));
        }
      }
    });
  }

  // Strategy 5 (last resort): scan bottom paragraphs for footnote-like content
  // Must have small font (≤10pt) — body text paragraphs are excluded
  if (footnotes.size === 0) {
    const allParagraphs = doc.querySelectorAll('p');
    const paragraphs = Array.from(allParagraphs);
    for (let i = paragraphs.length - 1; i >= 0; i--) {
      const p = paragraphs[i];
      const text = p.textContent?.trim() || '';
      const fnMatch = text.match(/^[\[\(]?(\d+)[\]\)]?\s+(.+)/);
      if (fnMatch) {
        const combinedStyle = (p.getAttribute('style') || '') +
          (p.querySelector('span[style]')?.getAttribute('style') || '');
        const sizeMatch = combinedStyle.match(/font-size\s*:\s*([\d.]+)\s*pt/i);
        if (sizeMatch && parseFloat(sizeMatch[1]) <= 10) {
          footnotes.set(fnMatch[1], fnMatch[2].trim());
          p.setAttribute('data-footnote-extracted', 'true');
        }
      } else if (footnotes.size > 0) {
        break;
      }
    }
  }

  return footnotes;
}

interface WalkContext {
  listDepth: number;
  listType?: 'ul' | 'ol';
  listIndex?: number;
}

function walkNode(node: Node, baselineSize: number, baselineFont: string, ctx: WalkContext, footnotes: Map<string, string>, fnRenumber: FootnoteRenumber): string {
  if (node.nodeType === Node.TEXT_NODE) {
    const text = node.textContent || '';
    // Collapse whitespace but preserve single spaces
    return text.replace(/[\r\n]+/g, ' ').replace(/\s+/g, ' ');
  }

  if (node.nodeType !== Node.ELEMENT_NODE) return '';

  const el = node as HTMLElement;
  const tag = el.tagName.toLowerCase();

  // Skip hidden elements
  if (el.style?.display === 'none') return '';

  // Skip extracted footnote containers
  if (el.getAttribute('data-footnote-extracted') === 'true') return '';

  // Skip footnote section divs (Word often wraps footnotes in a section)
  const elId = el.getAttribute('id') || '';
  if (/^_?(?:ftn|edn)\d+$/i.test(elId)) return '';

  // Helper: get or assign a new sequential number for a Word footnote
  const getNewFootnoteNum = (wordNum: string, text: string): number => {
    if (fnRenumber.mapping.has(wordNum)) return fnRenumber.mapping.get(wordNum)!;
    fnRenumber.counter++;
    const newNum = fnRenumber.counter;
    fnRenumber.mapping.set(wordNum, newNum);
    fnRenumber.used.set(newNum, text);
    return newNum;
  };

  // Get children content
  const childContent = () => {
    let result = '';
    for (let i = 0; i < el.childNodes.length; i++) {
      result += walkNode(el.childNodes[i], baselineSize, baselineFont, ctx, footnotes, fnRenumber);
    }
    return result;
  };

  switch (tag) {
    case 'br':
      return '  \n';

    case 'p':
    case 'div': {
      // Skip if this is a footnote section
      if (el.getAttribute('data-footnote-extracted') === 'true') return '';
      const content = childContent().trim();
      if (!content) return '\n';

      // Heuristic heading detection: short paragraph that is entirely bold
      // (Word often exports Hebrew headings as bold <p> rather than <h1>-<h6>)
      const headingLevel = detectHeadingLevel(el, content, baselineSize);
      if (headingLevel) {
        // Strip citation-font spans (headings have their own styling, not citations)
        // and strip outer bold markers since heading itself implies emphasis
        const cleanContent = content
          .replace(/<span class="citation-font">([\s\S]*?)<\/span>/g, '$1')
          .replace(/\*\*/g, '');  // Strip all bold markers — heading style implies emphasis
        return '#'.repeat(headingLevel) + ' ' + cleanContent + '\n\n';
      }

      return content + '\n\n';
    }

    case 'h1': return '# ' + childContent().trim() + '\n\n';
    case 'h2': return '## ' + childContent().trim() + '\n\n';
    case 'h3': return '### ' + childContent().trim() + '\n\n';
    case 'h4': return '#### ' + childContent().trim() + '\n\n';
    case 'h5': return '##### ' + childContent().trim() + '\n\n';
    case 'h6': return '###### ' + childContent().trim() + '\n\n';

    case 'b':
    case 'strong': {
      const content = childContent().trim();
      if (!content) return '';
      return `**${content}**`;
    }

    case 'i':
    case 'em': {
      const content = childContent().trim();
      if (!content) return '';
      // Check if this italic element itself carries a different font (Word sometimes sets font on <i>)
      const iStyle = el.getAttribute('style') || '';
      const iIsDiffFont = isDiffFont(iStyle, baselineFont);
      if (iIsDiffFont) return `<span class="citation-font">${content}</span>`;
      return `*${content}*`;
    }

    case 'u': {
      const content = childContent().trim();
      if (!content) return '';
      return `<u>${content}</u>`;
    }

    case 'sup': {
      // Check if this is inside a footnote reference link - just return content
      const content = childContent().trim();
      return content;
    }

    case 'blockquote': {
      const content = childContent().trim();
      const lines = content.split('\n').map(l => '> ' + l);
      return lines.join('\n') + '\n\n';
    }

    case 'ul': {
      let result = '';
      for (let i = 0; i < el.childNodes.length; i++) {
        const child = el.childNodes[i];
        if (child.nodeType === Node.ELEMENT_NODE && (child as HTMLElement).tagName.toLowerCase() === 'li') {
          const indent = '  '.repeat(ctx.listDepth);
          const content = walkNode(child, baselineSize, baselineFont, { ...ctx, listDepth: ctx.listDepth + 1, listType: 'ul' }, footnotes, fnRenumber);
          result += `${indent}- ${content.trim()}\n`;
        }
      }
      return result + '\n';
    }

    case 'ol': {
      let idx = 1;
      let result = '';
      for (let i = 0; i < el.childNodes.length; i++) {
        const child = el.childNodes[i];
        if (child.nodeType === Node.ELEMENT_NODE && (child as HTMLElement).tagName.toLowerCase() === 'li') {
          const indent = '  '.repeat(ctx.listDepth);
          const content = walkNode(child, baselineSize, baselineFont, { ...ctx, listDepth: ctx.listDepth + 1, listType: 'ol', listIndex: idx }, footnotes, fnRenumber);
          result += `${indent}${idx}. ${content.trim()}\n`;
          idx++;
        }
      }
      return result + '\n';
    }

    case 'li': {
      return childContent();
    }

    case 'a': {
      const href = el.getAttribute('href') || '';

      // Check if this is a footnote/endnote reference link
      const ftnMatch = href.match(/#_?(?:ftn|edn)(?:ref)?(\d+)/i);
      if (ftnMatch) {
        const num = ftnMatch[1];
        const footnoteText = footnotes.get(num) || '';
        // Always create footnote marker, even if definition text is missing
        const newNum = getNewFootnoteNum(num, footnoteText);
        return `[^${newNum}]`;
      }

      // Check if this is a footnote back-reference (skip it)
      const nameAttr = el.getAttribute('name') || '';
      if (/^_?(?:ftn|edn)(?:ref)?\d+$/i.test(nameAttr)) {
        // This is inside the footnote section, just return content
        return childContent();
      }

      // Regular link
      const content = childContent().trim();
      if (href && content && !href.startsWith('#')) return `[${content}](${href})`;
      return content;
    }

    case 'span': {
      let content = childContent();
      if (!content.trim()) return content;

      const style = el.getAttribute('style') || '';

      // Check if this is a footnote reference (vertical-align:super with a number)
      if (/vertical-align\s*:\s*super/i.test(style)) {
        // This might be a footnote number not wrapped in <a>
        const trimmedContent = content.trim();
        const numMatch = trimmedContent.match(/^\d+$/);
        if (numMatch) {
          const footnoteText = footnotes.get(trimmedContent) || '';
          const newNum = getNewFootnoteNum(trimmedContent, footnoteText);
          return `[^${newNum}]`;
        }
      }

      // Check for bold
      const isBold = isBoldStyle(style);
      // Check for underline
      const isUnderline = /text-decoration\s*:[^;]*underline/i.test(style);
      // Check for italic (including mso-bidi/mso-ansi variants for Hebrew/RTL)
      const isItalic = /(?:^|;|\s)font-style\s*:\s*italic/i.test(style)
        || /mso-(?:bidi|ansi)-font-style\s*:\s*italic/i.test(style);
      // Check for small font
      const isSmall = isSmallFont(style, baselineSize);
      // Check for different font (citations/quotes) — also check inherited from parent
      const isDifferentFont = isDiffFont(style, baselineFont)
        || (!extractFontFamily(style) && getInheritedFont(el, baselineFont));

      const trimmed = content.trim();

      // Debug: log font detection for non-empty spans
      if (trimmed.length > 5 && trimmed.length < 200) {
        const spanFont = extractFontFamily(style);
        if (spanFont || isDifferentFont) {
          console.log('[Word→MD] span font:', spanFont || '(inherited)', '| isDiff:', isDifferentFont, '| text:', trimmed.substring(0, 50));
        }
      }
      const leadingSpace = content.startsWith(' ') ? ' ' : '';
      const trailingSpace = content.endsWith(' ') ? ' ' : '';

      let result = trimmed;
      if (isDifferentFont) result = `<span class="citation-font">${result}</span>`;
      if (isSmall) result = `<small>${result}</small>`;
      if (isUnderline) result = `<u>${result}</u>`;
      // Skip italic wrapping for citation-font text — the font change is the indicator
      if (isItalic && !isDifferentFont) result = `*${result}*`;
      if (isBold) result = `**${result}**`;

      return leadingSpace + result + trailingSpace;
    }

    // Skip these entirely
    case 'script':
    case 'style':
    case 'img':
    case 'table':
    case 'thead':
    case 'tbody':
    case 'tr':
    case 'td':
    case 'th':
      return '';

    default:
      return childContent();
  }
}

function isBoldStyle(style: string): boolean {
  const weightMatch = style.match(/font-weight\s*:\s*(\w+)/i);
  if (!weightMatch) return false;
  const weight = weightMatch[1].toLowerCase();
  if (weight === 'bold' || weight === 'bolder') return true;
  const numWeight = parseInt(weight);
  return !isNaN(numWeight) && numWeight >= 700;
}

function isSmallFont(style: string, baselineSize: number): boolean {
  const match = style.match(/font-size\s*:\s*([\d.]+)\s*(pt|px|em|%)/i);
  if (!match) return false;

  const size = parseFloat(match[1]);
  const unit = match[2].toLowerCase();

  // Convert to pt for comparison
  let sizeInPt: number;
  if (unit === 'pt') sizeInPt = size;
  else if (unit === 'px') sizeInPt = size * 0.75; // 1px ≈ 0.75pt
  else if (unit === 'em') sizeInPt = size * baselineSize;
  else if (unit === '%') sizeInPt = (size / 100) * baselineSize;
  else return false;

  // Consider "small" if less than 80% of baseline
  return sizeInPt < baselineSize * 0.8;
}

/** Extracts the primary font-family name from a style string.
 *  For Hebrew/RTL text, Word uses mso-bidi-font-family instead of font-family,
 *  so we check both and prefer the bidi variant. */
function extractFontFamily(style: string): string {
  // Try mso-bidi-font-family first (Hebrew/RTL font)
  const bidiMatch = style.match(/mso-bidi-font-family\s*:\s*['"]?([^'",;]+)/i);
  if (bidiMatch) return bidiMatch[1].trim().toLowerCase();
  // Fall back to standard font-family
  const match = style.match(/font-family\s*:\s*['"]?([^'",;]+)/i);
  if (!match) return '';
  return match[1].trim().toLowerCase();
}

/** Normalizes a font name by stripping weight/style variants.
 *  "David Bold" → "david", "Arial Italic" → "arial" */
function normalizeFontName(font: string): string {
  return font
    .replace(/\b(bold|italic|light|medium|regular|thin|black|semi-?bold|demi-?bold|extra-?bold|extra-?light|condensed|expanded|narrow|wide|oblique)\b/gi, '')
    .replace(/\s+/g, ' ')
    .trim();
}

/** Checks if a span uses a different font than the baseline */
function isDiffFont(style: string, baselineFont: string): boolean {
  const font = extractFontFamily(style);
  if (!font) return false; // No explicit font on this element
  // Ignore generic families
  const generic = ['serif', 'sans-serif', 'monospace', 'cursive', 'fantasy', 'system-ui'];
  if (generic.includes(font)) return false;
  // If baseline is implicit (most text has no explicit font), any non-generic explicit font is different
  if (!baselineFont) return true;
  if (font === baselineFont) return false;
  // Ignore weight/style variants (e.g., "David Bold" vs "David")
  if (normalizeFontName(font) === normalizeFontName(baselineFont)) return false;
  return true;
}

/** Walks up DOM tree to find the nearest ancestor with a font-family style */
function getInheritedFont(el: HTMLElement | null, baselineFont: string): boolean {
  let current = el?.parentElement;
  while (current && current.tagName.toLowerCase() !== 'body') {
    const style = current.getAttribute('style') || '';
    if (isDiffFont(style, baselineFont)) return true;
    // If this element specifies a font that matches baseline, stop searching
    const font = extractFontFamily(style);
    if (font) return false;
    current = current.parentElement;
  }
  return false;
}

/** Detects the most common font-family in the document.
 *  Normalizes font names so "David Bold" and "David" are counted together.
 *  Returns '' if most text has no explicit font (meaning baseline is the implicit default). */
function detectBaselineFont(body: HTMLElement): string {
  const fonts: Map<string, number> = new Map();
  let implicitFontChars = 0;

  function scanElement(el: HTMLElement) {
    const style = el.getAttribute('style') || '';
    const font = extractFontFamily(style);
    if (font) {
      // Normalize to group weight/style variants together
      const normalized = normalizeFontName(font);
      if (normalized) {
        fonts.set(normalized, (fonts.get(normalized) || 0) + (el.textContent?.length || 0));
      }
    } else {
      // Count direct text nodes (not descendant text) for elements without explicit font
      for (let i = 0; i < el.childNodes.length; i++) {
        if (el.childNodes[i].nodeType === 3) { // TEXT_NODE
          implicitFontChars += (el.childNodes[i].textContent?.length || 0);
        }
      }
    }
    for (let i = 0; i < el.children.length; i++) {
      scanElement(el.children[i] as HTMLElement);
    }
  }

  scanElement(body);

  if (fonts.size === 0) return '';

  let maxCount = 0;
  let baseline = '';
  fonts.forEach((count, font) => {
    if (count > maxCount) {
      maxCount = count;
      baseline = font;
    }
  });

  // If most text has no explicit font, the baseline is the implicit/default font
  if (implicitFontChars > maxCount) return '';

  return baseline;
}

function detectBaselineFontSize(body: HTMLElement): number {
  const sizes: Map<number, number> = new Map();

  function scanElement(el: HTMLElement) {
    const style = el.getAttribute('style') || '';
    const match = style.match(/font-size\s*:\s*([\d.]+)\s*(pt|px)/i);
    if (match) {
      let sizeInPt: number;
      const size = parseFloat(match[1]);
      const unit = match[2].toLowerCase();
      if (unit === 'pt') sizeInPt = size;
      else sizeInPt = size * 0.75;

      sizes.set(sizeInPt, (sizes.get(sizeInPt) || 0) + (el.textContent?.length || 0));
    }
    for (let i = 0; i < el.children.length; i++) {
      scanElement(el.children[i] as HTMLElement);
    }
  }

  scanElement(body);

  if (sizes.size === 0) return 12; // Default Word body text size

  // Find the most common font size (weighted by text length)
  let maxCount = 0;
  let baseline = 12;
  sizes.forEach((count, size) => {
    if (count > maxCount) {
      maxCount = count;
      baseline = size;
    }
  });

  return baseline;
}

/**
 * Detects if a <p> element looks like a heading based on heuristics:
 * - Short text (≤80 chars)
 * - Entirely bold (all text wrapped in <b>/<strong> or bold spans)
 * - Optionally: larger font size than baseline
 * Returns heading level (2 or 3) or false.
 */
function detectHeadingLevel(el: HTMLElement, markdownContent: string, baselineSize: number): number | false {
  const textContent = el.textContent?.trim() || '';
  if (!textContent) return false;

  // Priority 1: Word heading class (MsoHeading1, MsoHeading2, etc.)
  const wordLevel = el.getAttribute('data-word-heading');
  if (wordLevel) {
    const level = parseInt(wordLevel);
    if (level >= 1 && level <= 6) return Math.max(level + 1, 2); // Shift down: Word H1→##, H2→###
  }

  // Priority 2: Heuristic detection for unlabeled headings
  if (textContent.length > 80) return false;

  // Don't treat list-like lines as headings
  if (/^[\-•·]\s/.test(textContent) || /^\d+[.)]\s/.test(textContent)) return false;

  // Check if all text in this paragraph is bold
  const allBold = isEntirelyBold(el, false);

  // Check font size ratio compared to baseline
  const fontRatio = getParagraphFontRatio(el, baselineSize);

  if (allBold && fontRatio > 1.15) return 2; // Bold + larger font → ##
  if (fontRatio > 1.35) return 2;            // Very large font (even without bold) → ##
  if (allBold && textContent.length <= 60) return 3; // Short bold text → ###

  return false;
}

/** Recursively checks if all text in an element is inside bold tags/styles */
function isEntirelyBold(el: HTMLElement, parentIsBold: boolean): boolean {
  for (let i = 0; i < el.childNodes.length; i++) {
    const child = el.childNodes[i];
    if (child.nodeType === Node.TEXT_NODE) {
      if (child.textContent?.trim() && !parentIsBold) return false;
    } else if (child.nodeType === Node.ELEMENT_NODE) {
      const childEl = child as HTMLElement;
      const tag = childEl.tagName.toLowerCase();
      const childIsBold = parentIsBold
        || tag === 'b' || tag === 'strong'
        || isBoldStyle(childEl.getAttribute('style') || '');
      if (!isEntirelyBold(childEl, childIsBold)) return false;
    }
  }
  return true;
}

/** Gets the font-size ratio of a paragraph relative to the baseline */
function getParagraphFontRatio(el: HTMLElement, baselineSize: number): number {
  // Check inline style of the paragraph itself
  const style = el.getAttribute('style') || '';
  const match = style.match(/font-size\s*:\s*([\d.]+)\s*(pt|px)/i);
  if (match) {
    const size = parseFloat(match[1]);
    const sizeInPt = match[2].toLowerCase() === 'pt' ? size : size * 0.75;
    return sizeInPt / baselineSize;
  }

  // Check first child with a font-size style
  const spans = el.querySelectorAll('span[style]');
  for (let i = 0; i < spans.length; i++) {
    const spanStyle = spans[i].getAttribute('style') || '';
    const spanMatch = spanStyle.match(/font-size\s*:\s*([\d.]+)\s*(pt|px)/i);
    if (spanMatch) {
      const size = parseFloat(spanMatch[1]);
      const sizeInPt = spanMatch[2].toLowerCase() === 'pt' ? size : size * 0.75;
      return sizeInPt / baselineSize;
    }
  }

  return 1.0;
}

function cleanMarkdown(md: string, usedFootnotes: Map<number, string>): string {
  let result = md;

  // Remove zero-width spaces
  result = result.replace(/\u200B/g, '');
  // Replace non-breaking spaces with regular spaces
  result = result.replace(/\u00A0/g, ' ');

  // Clean bracket annotations [=...] - Word may split brackets across spans
  // Case 1: [<small>=annotation</small>] - tags INSIDE brackets
  result = result.replace(/\[<[^>]+>=([\s\S]*?)<\/[^>]+>\]/g, '[=$1]');
  // Case 2: <small>[=annotation]</small> - tags OUTSIDE brackets
  result = result.replace(/<[^>]+>(\[=[^\]]+\])<\/[^>]+>/g, '$1');
  result = result.replace(/<[^>]+>(\[=[^\]]+\])/g, '$1');
  result = result.replace(/(\[=[^\]]+\])<\/[^>]+>/g, '$1');
  // Case 3: strip any remaining HTML tags from inside [=...]
  result = result.replace(/\[=([\s\S]*?)\]/g, (match, inner) => {
    const cleaned = inner.replace(/<[^>]*>/g, '');
    return `[=${cleaned}]`;
  });

  // Convert bracket annotations [=הערה] to tooltips
  // The word before the bracket becomes the anchor text
  result = result.replace(/([\p{L}\p{N}]+)\s*\[=([^\]]+)\]/gu, (_, word, annotation) => {
    return `[${word}](tooltip:${annotation.trim()})`;
  });

  // Collapse 3+ newlines into 2
  result = result.replace(/\n{3,}/g, '\n\n');
  // Remove trailing spaces on lines (except markdown line breaks: 2 spaces + \n)
  result = result.replace(/([^ \n]) +\n/g, '$1\n');
  // Trim
  result = result.trim();

  // Append footnote definitions at the end (renumbered from 1)
  if (usedFootnotes.size > 0) {
    result += '\n\n';
    const sorted = Array.from(usedFootnotes.entries()).sort((a, b) => a[0] - b[0]);
    for (const [num, text] of sorted) {
      result += `[^${num}]: ${text}\n`;
    }
    result = result.trimEnd();
  }

  return result;
}
