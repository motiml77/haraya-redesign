/**
 * Converts Google Docs–pasted HTML to Markdown.
 *
 * Google Docs wraps pasted content in:
 *   <b id="docs-internal-guid-..."> ... </b>
 * where the <b> is NOT semantic bold — it's just a container.
 *
 * Formatting is expressed via inline styles on <span> elements:
 *   font-weight: 700           → bold
 *   font-style: italic         → italic
 *   text-decoration: underline → underline
 *   font-size: Xpt             → detect heading / small
 *   vertical-align: super      → superscript (footnotes)
 *
 * This converter handles those patterns and emits Markdown.
 */
export function convertGoogleDocsHtmlToMarkdown(html: string): string {
  // Step 1: Parse
  const parser = new DOMParser();
  const doc = parser.parseFromString(html, 'text/html');

  // Step 2: Unwrap the Google Docs wrapper <b id="docs-internal-guid-...">
  // This wrapper is NOT bold — it's a container element.
  const wrappers = doc.querySelectorAll('b[id^="docs-internal-guid"]');
  wrappers.forEach(wrapper => {
    const parent = wrapper.parentNode;
    if (!parent) return;
    while (wrapper.firstChild) {
      parent.insertBefore(wrapper.firstChild, wrapper);
    }
    parent.removeChild(wrapper);
  });

  // Step 3: Detect baseline font size
  const baselineSize = detectBaselineSize(doc.body);

  // Step 4: Walk the DOM
  const markdown = walkNode(doc.body, baselineSize);

  // Step 5: Clean up
  return cleanMarkdown(markdown);
}

function detectBaselineSize(body: HTMLElement): number {
  const sizes = new Map<number, number>();

  function scan(el: HTMLElement) {
    const style = el.getAttribute('style') || '';
    const match = style.match(/font-size\s*:\s*([\d.]+)\s*(pt|px)/i);
    if (match) {
      const size = parseFloat(match[1]);
      const unit = match[2].toLowerCase();
      const sizeInPt = unit === 'pt' ? size : size * 0.75;
      sizes.set(sizeInPt, (sizes.get(sizeInPt) || 0) + (el.textContent?.length || 0));
    }
    for (let i = 0; i < el.children.length; i++) {
      scan(el.children[i] as HTMLElement);
    }
  }

  scan(body);

  if (sizes.size === 0) return 11; // Google Docs default is 11pt

  let maxCount = 0;
  let baseline = 11;
  sizes.forEach((count, size) => {
    if (count > maxCount) {
      maxCount = count;
      baseline = size;
    }
  });
  return baseline;
}

function walkNode(node: Node, baselineSize: number): string {
  if (node.nodeType === Node.TEXT_NODE) {
    return (node.textContent || '').replace(/[\r\n]+/g, ' ').replace(/\s+/g, ' ');
  }

  if (node.nodeType !== Node.ELEMENT_NODE) return '';

  const el = node as HTMLElement;
  const tag = el.tagName.toLowerCase();

  if (el.style?.display === 'none') return '';

  const childContent = (): string => {
    let result = '';
    for (let i = 0; i < el.childNodes.length; i++) {
      result += walkNode(el.childNodes[i], baselineSize);
    }
    return result;
  };

  switch (tag) {
    case 'br':
      return '  \n';

    case 'p': {
      const content = childContent().trim();
      if (!content) return '\n';
      // No automatic heading detection — paragraphs stay as paragraphs.
      // Users insert explicit headings via the toolbar's H button.
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
      return `*${content}*`;
    }

    case 'u': {
      const content = childContent().trim();
      if (!content) return '';
      return `<u>${content}</u>`;
    }

    case 'sup': {
      return childContent();
    }

    case 'a': {
      const href = el.getAttribute('href') || '';
      const content = childContent().trim();
      if (href && content && !href.startsWith('#')) return `[${content}](${href})`;
      return content;
    }

    case 'ul': {
      let result = '';
      el.querySelectorAll(':scope > li').forEach(li => {
        const content = walkNode(li, baselineSize);
        result += `- ${content.trim()}\n`;
      });
      return result + '\n';
    }

    case 'ol': {
      let result = '';
      let idx = 1;
      el.querySelectorAll(':scope > li').forEach(li => {
        const content = walkNode(li, baselineSize);
        result += `${idx}. ${content.trim()}\n`;
        idx++;
      });
      return result + '\n';
    }

    case 'li':
      return childContent();

    case 'span': {
      let content = childContent();
      if (!content.trim()) return content;

      const style = el.getAttribute('style') || '';

      // Detect formatting from inline styles
      const isBold = /font-weight\s*:\s*(bold|[7-9]\d\d)/i.test(style);
      const isItalic = /font-style\s*:\s*italic/i.test(style);
      const isUnderline = /text-decoration\s*:[^;]*underline/i.test(style);
      const isSmall = isSmallFont(style, baselineSize);
      const isSuperscript = /vertical-align\s*:\s*super/i.test(style);

      // Preserve leading/trailing whitespace
      const leadingSpace = content.startsWith(' ') ? ' ' : '';
      const trailingSpace = content.endsWith(' ') ? ' ' : '';
      let result = content.trim();

      if (isSuperscript) return result; // Just return the text for superscripts
      if (isSmall) result = `<small>${result}</small>`;
      if (isUnderline) result = `<u>${result}</u>`;
      if (isItalic) result = `*${result}*`;
      if (isBold) result = `**${result}**`;

      return leadingSpace + result + trailingSpace;
    }

    case 'div':
      return childContent();

    case 'style':
    case 'script':
    case 'img':
      return '';

    default:
      return childContent();
  }
}

function isSmallFont(style: string, baselineSize: number): boolean {
  const match = style.match(/font-size\s*:\s*([\d.]+)\s*(pt|px)/i);
  if (!match) return false;
  const size = parseFloat(match[1]);
  const unit = match[2].toLowerCase();
  const sizeInPt = unit === 'pt' ? size : size * 0.75;
  return sizeInPt < baselineSize * 0.8;
}

function cleanMarkdown(md: string): string {
  let result = md;

  // Remove zero-width spaces
  result = result.replace(/​/g, '');
  // Replace non-breaking spaces
  result = result.replace(/ /g, ' ');

  // Fix nested bold markers: ****text**** → **text**
  result = result.replace(/\*{3,}([^*]+)\*{3,}/g, '**$1**');

  // Collapse 3+ newlines into 2
  result = result.replace(/\n{3,}/g, '\n\n');
  // Remove trailing spaces
  result = result.replace(/([^ \n]) +\n/g, '$1\n');

  return result.trim();
}
