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

  // Build a map for quick lookup when prefetching children
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
        // Prefetch children pages in background when expanding
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
    <>
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
    </>
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

  const indent = depth === 0 ? '' : depth === 1 ? 'mr-4' : 'mr-8';
  const textSize = depth === 0 ? 'text-base' : 'text-sm';

  // If section has content and no children — direct link
  if (section.hasContent && !hasChildren) {
    return (
      <Link href={`/book/${bookId}/${section.id}`}
        className={`flex items-center gap-2 bg-white p-3 rounded-xl shadow-sm border border-[#E5E0D8] hover:border-[#8C2B2B] hover:shadow-md transition-all group ${indent}`}>
        <FileText size={16} className="text-[#8C7A6B] group-hover:text-[#8C2B2B] transition-colors shrink-0" />
        <span className={`${textSize} font-bold text-[#4A3B32] flex-1`}>{section.title}</span>
        <span className={`w-2 h-2 rounded-full shrink-0 ${section.isEdited ? 'bg-green-500' : 'bg-red-400'}`}
          title={section.isEdited ? 'ערוך' : 'לא ערוך'}></span>
      </Link>
    );
  }

  // Container with children (may also have content)
  return (
    <div className={`bg-white rounded-xl shadow-sm border border-[#E5E0D8] overflow-hidden ${indent}`}>
      <div className="flex items-center">
        {section.hasContent ? (
          <Link href={`/book/${bookId}/${section.id}`}
            className="flex-1 flex items-center gap-2 p-3 hover:bg-[#FAF8F5] transition-colors text-right">
            <h2 className={`${textSize} font-bold text-[#4A3B32]`}>{section.title}</h2>
            {section.hasContent && (
              <span className={`w-2 h-2 rounded-full shrink-0 ${section.isEdited ? 'bg-green-500' : 'bg-red-400'}`}></span>
            )}
          </Link>
        ) : (
          <button onClick={() => onToggle(section.id)}
            className="flex-1 flex items-center gap-2 p-3 hover:bg-[#FAF8F5] transition-colors text-right">
            <h2 className={`${textSize} font-bold text-[#4A3B32]`}>{section.title}</h2>
          </button>
        )}
        {hasChildren && (
          <button onClick={() => onToggle(section.id)} className="p-3">
            <ChevronDown size={18} className={`text-[#8C7A6B] transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
          </button>
        )}
      </div>

      {isExpanded && hasChildren && (
        <div className="border-t border-[#E5E0D8] p-3 space-y-2">
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
