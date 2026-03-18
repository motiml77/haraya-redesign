import { ContentBlock } from './types';

/**
 * Normalizes a section to use contentBlocks.
 * Converts legacy originalText + commentary[] format on read.
 */
export function normalizeSectionContent(section: any): any {
  if (section.contentBlocks && section.contentBlocks.length > 0) {
    return section;
  }

  const blocks: ContentBlock[] = [];

  if (section.originalText) {
    const commentaries = section.commentary || [];

    if (commentaries.length === 0) {
      blocks.push({ id: 'cb_migrated_0', sourceText: section.originalText, commentaryText: '' });
    } else if (commentaries.length === 1) {
      blocks.push({ id: 'cb_migrated_0', sourceText: section.originalText, commentaryText: commentaries[0].text });
    } else {
      blocks.push({ id: 'cb_migrated_0', sourceText: section.originalText, commentaryText: commentaries[0].text });
      commentaries.slice(1).forEach((c: any, i: number) => {
        blocks.push({ id: `cb_migrated_${i + 1}`, sourceText: '', commentaryText: c.text });
      });
    }
  }

  return { ...section, contentBlocks: blocks };
}
