'use client';

import React, { useState, useMemo, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ChevronDown, FileText } from 'lucide-react';

export interface SectionNode {
  id: string;
  title: string;
  parentId: string | null;
  depth: number;
  orderIndex: number;
  hasContent: boolean;
  isEdited?: boolean;
  children: SectionNode[];
}

function buildTree(flatSections: any[]): SectionNode[] {
  const map = new Map<string, SectionNode>();
  const roots: SectionNode[] = [];

  flatSections.forEach(s => {
    map.set(s.id, { ...s, children: [] });
  });

  flatSections.forEach(s => {
    const node = map.get(s.id)!;
    if (s.parentId && map.has(s.parentId)) {
      map.get(s.parentId)!.children.push(node);
    } else {
      roots.push(node);
    }
  });

  const sortChildren = (nodes: SectionNode[]) => {
    nodes.sort((a, b) => (a.orderIndex || 0) - (b.orderIndex || 0));
    nodes.forEach(n => sortChildren(n.children));
  };
  sortChildren(roots);

  return roots;
}

export function BookSectionsTree({ sections: flatSections, bookId }: { sections: any[]; bookId: string }) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
  const tree = useMemo(() => buildTree(flatSections || []), [flatSections]);
  const router = useRouter();

  const nodeMap = useMemo(() => {
    const map = new Map<string, SectionNode>();
    const addToMap = (nodes: SectionNode[]) => {
      nodes.forEach(n => { map.set(n.id, n); addToMap(n.children); });
    };
    addToMap(tree);
    return map;
  }, [tree]);

  const toggleSection = useCallback((sectionId: string) => {
    setExpandedSections(prev => {
      const next = new Set(prev);
      if (next.has(sectionId)) {
        next.delete(sectionId);
      } else {
        next.add(sectionId);
        const node = nodeMap.get(sectionId);
        if (node) {
          node.children.forEach(child => {
            if (child.hasContent) {
              router.prefetch(`/book/${bookId}/${child.id}`);
            }
          });
        }
      }
      return next;
    });
  }, [nodeMap, bookId, router]);

  if (tree.length === 0) return null;

  return (
    <div className="space-y-2">
      {tree.map(section => (
        <SectionCard
          key={section.id}
          section={section}
          bookId={bookId}
          expandedSections={expandedSections}
          onToggle={toggleSection}
          depth={0}
        />
      ))}
    </div>
  );
}

function SectionCard({ section, bookId, expandedSections, onToggle, depth }: {
  section: SectionNode;
  bookId: string;
  expandedSections: Set<string>;
  onToggle: (id: string) => void;
  depth: number;
}) {
  const hasChildren = section.children.length > 0;
  const isExpanded = expandedSections.has(section.id);

  const indent = depth === 0 ? '' : depth === 1 ? 'mr-6' : 'mr-12';
  const titleSize = depth === 0 ? 'text-lg' : depth === 1 ? 'text-base' : 'text-sm';

  // If section has content and no children — direct link
  if (section.hasContent && !hasChildren) {
    return (
      <Link href={`/book/${bookId}/${section.id}`}
        className={`flex items-center gap-3 bg-[#E8DCC4] px-4 py-3 border border-[#D6C8A8] hover:border-[#B14F1C] hover:bg-[#F1E6D2] transition-all group ${indent}`}>
        <FileText size={15} className="text-[#B14F1C] shrink-0" />
        <span className={`${titleSize} font-serif font-semibold text-[#1F1A14] flex-1 group-hover:text-[#B14F1C] transition-colors`}>{section.title}</span>
        <span className={`w-2 h-2 rounded-full shrink-0 ${section.isEdited ? 'bg-[#3F5C3F]' : 'bg-[#B85450]'}`}
          title={section.isEdited ? 'ערוך' : 'לא ערוך'}></span>
        <span className="text-xs text-[#B14F1C] font-bold opacity-0 group-hover:opacity-100 transition-opacity">קרא ←</span>
      </Link>
    );
  }

  // Container with children
  return (
    <div className={`bg-[#E8DCC4] border border-[#D6C8A8] overflow-hidden ${indent}`}>
      <div className="flex items-center">
        {section.hasContent ? (
          <Link href={`/book/${bookId}/${section.id}`}
            className="flex-1 flex items-center gap-3 px-4 py-3 hover:bg-[#F1E6D2] transition-colors text-right">
            <h2 className={`${titleSize} font-serif font-semibold text-[#1F1A14]`}>{section.title}</h2>
            <span className={`w-2 h-2 rounded-full shrink-0 ${section.isEdited ? 'bg-[#3F5C3F]' : 'bg-[#B85450]'}`}></span>
          </Link>
        ) : (
          <button onClick={() => onToggle(section.id)}
            className="flex-1 flex items-center gap-3 px-4 py-3 hover:bg-[#F1E6D2] transition-colors text-right">
            <h2 className={`${titleSize} font-serif font-semibold text-[#1F1A14]`}>{section.title}</h2>
          </button>
        )}
        {hasChildren && (
          <button onClick={() => onToggle(section.id)} className="px-4 py-3" aria-label="הרחב/כווץ">
            <ChevronDown size={16} className={`text-[#B14F1C] transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
          </button>
        )}
      </div>

      {isExpanded && hasChildren && (
        <div className="border-t border-dashed border-[#D6C8A8] bg-[#F1E6D2] px-4 py-3 space-y-2">
          {section.children.map(child => (
            <SectionCard
              key={child.id}
              section={child}
              bookId={bookId}
              expandedSections={expandedSections}
              onToggle={onToggle}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}
