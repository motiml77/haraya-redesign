import React from 'react';
import { adminDb } from '@/lib/firebase-admin';
import { getCached, setCache } from '@/lib/cache';
import { SectionViewer } from '@/components/SectionViewer';

export const revalidate = 60;

// Pre-build section pages with content at build time
export async function generateStaticParams() {
  try {
    const snapshot = await adminDb.collection('sections')
      .where('originalText', '!=', '')
      .get();
    return snapshot.docs.map(doc => ({
      bookId: doc.data().bookId,
      sectionId: doc.id,
    }));
  } catch {
    return [];
  }
}

async function getSection(sectionId: string) {
  const cacheKey = `sections:${sectionId}`;
  const cached = getCached<any>(cacheKey);
  if (cached) return cached;

  const doc = await adminDb.collection('sections').doc(sectionId).get();
  if (!doc.exists) return null;

  const result = { id: doc.id, ...doc.data() };
  setCache(cacheKey, result, 30_000);
  return result;
}

async function getBookWithSections(bookId: string) {
  const cacheKey = `books:${bookId}`;
  const cached = getCached<any>(cacheKey);
  if (cached) return cached;

  const [doc, sectionsSnap] = await Promise.all([
    adminDb.collection('books').doc(bookId).get(),
    adminDb.collection('sections').where('bookId', '==', bookId).get(),
  ]);

  if (!doc.exists) return null;

  const sections = sectionsSnap.docs
    .filter(d => !d.data().isHidden)
    .map(d => ({
      id: d.id,
      title: d.data().title,
      bookId: d.data().bookId,
      parentId: d.data().parentId,
      orderIndex: d.data().orderIndex,
      isEdited: d.data().isEdited,
      hasContent: !!(d.data().originalText),
    })).sort((a: any, b: any) => (a.orderIndex || 0) - (b.orderIndex || 0));

  const result = { id: doc.id, ...doc.data(), sections };
  setCache(cacheKey, result, 60_000);
  return result;
}

export default async function SectionPage({ params }: { params: Promise<{ bookId: string; sectionId: string }> }) {
  const { bookId, sectionId } = await params;
  
  const [section, book] = await Promise.all([
    getSection(sectionId),
    getBookWithSections(bookId),
  ]);

  if (!section || !book) {
    return <div className="min-h-screen bg-[#FAF8F5] flex items-center justify-center text-[#8C2B2B] font-serif text-xl" suppressHydrationWarning>התוכן לא נמצא</div>;
  }

  // Flatten tree to reading order (depth-first) for sequential navigation
  function flattenSections(sections: any[]): any[] {
    const roots = sections
      .filter((s: any) => !s.parentId)
      .sort((a: any, b: any) => (a.orderIndex || 0) - (b.orderIndex || 0));

    const result: any[] = [];
    const addWithChildren = (node: any) => {
      if (node.hasContent) result.push(node);
      sections
        .filter((s: any) => s.parentId === node.id)
        .sort((a: any, b: any) => (a.orderIndex || 0) - (b.orderIndex || 0))
        .forEach(addWithChildren);
    };
    roots.forEach(addWithChildren);
    return result;
  }

  const siblings = flattenSections(book.sections);

  // Build breadcrumbs
  const breadcrumbItems: { label: string; href?: string }[] = [
    { label: 'ספרים', href: '/' },
    { label: book.title || section.bookTitle || '', href: `/book/${bookId}` },
  ];

  if (section.parentId && book.sections) {
    const sectionMap = new Map(book.sections.map((s: any) => [s.id, s]));
    const ancestors: { title: string; id: string }[] = [];
    let currentId = section.parentId;
    while (currentId) {
      const parent = sectionMap.get(currentId) as any;
      if (parent) {
        ancestors.unshift({ title: parent.title, id: parent.id });
        currentId = parent.parentId;
      } else break;
    }
    ancestors.forEach(a => {
      breadcrumbItems.push({ label: a.title, href: `/book/${bookId}/${a.id}` });
    });
  }
  breadcrumbItems.push({ label: section.title });

  return (
    <SectionViewer 
      initialSection={section} 
      book={book} 
      siblings={siblings} 
      breadcrumbItems={breadcrumbItems} 
    />
  );
}
