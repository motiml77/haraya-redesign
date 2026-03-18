import React from 'react';
import Link from 'next/link';
import { BookOpen } from 'lucide-react';
import { adminDb } from '@/lib/firebase-admin';
import { getCached, setCache } from '@/lib/cache';
import { Breadcrumb } from '@/components/Breadcrumb';
import { PageHeaderAuth } from '@/components/PageHeaderAuth';
import { BookSectionsTree } from '@/components/BookSectionsTree';

export const revalidate = 60; // Revalidate every 60 seconds

// Pre-build all book pages at build time for instant loading
export async function generateStaticParams() {
  try {
    const snapshot = await adminDb.collection('books').get();
    return snapshot.docs.map(doc => ({ bookId: doc.id }));
  } catch {
    return [];
  }
}

async function getBookWithSections(bookId: string) {
  const cacheKey = `books:${bookId}`;
  const cached = getCached<any>(cacheKey);
  if (cached) return cached;

  try {
    const [doc, sectionsSnap] = await Promise.all([
      adminDb.collection('books').doc(bookId).get(),
      adminDb.collection('sections').where('bookId', '==', bookId).get(),
    ]);

    if (!doc.exists) return null;

    const sections = sectionsSnap.docs
      .filter(d => !d.data().isHidden)
      .map(d => ({
        id: d.id,
        ...d.data(),
        hasContent: !!(d.data().originalText || (d.data().contentBlocks && d.data().contentBlocks.length > 0)),
      })).sort((a: any, b: any) => (a.orderIndex || 0) - (b.orderIndex || 0));

    const result = { id: doc.id, ...doc.data(), sections };
    setCache(cacheKey, result, 60_000);
    return result;
  } catch (error) {
    console.error('Error fetching book for SSR:', error);
    return null;
  }
}

export default async function BookPage({ params }: { params: Promise<{ bookId: string }> }) {
  const { bookId } = await params;
  const book = await getBookWithSections(bookId);

  if (!book) return <div className="min-h-screen bg-[#FAF8F5] flex items-center justify-center text-[#8C2B2B] font-serif text-xl" suppressHydrationWarning>ספר לא נמצא</div>;

  return (
    <div className="min-h-screen bg-[#FAF8F5] font-sans" dir="rtl">
      <header className="bg-white border-b border-[#E5E0D8] py-6 px-6">
        <div className="max-w-4xl mx-auto flex items-start gap-4">
          <Link href="/" className="p-2 rounded-full hover:bg-[#F0EBE1] transition-colors mt-1 shrink-0" title="חזרה לדף הראשי">
            <BookOpen size={28} className="text-[#8C2B2B]" />
          </Link>
          <div className="flex-1">
            <Breadcrumb items={[
              { label: 'ספרים', href: '/' },
              { label: book.title },
            ]} />
            <h1 className="text-3xl font-serif font-bold text-[#4A3B32] mt-4">{book.title}</h1>
            {book.description && <p className="text-[#8C7A6B] mt-2">{book.description}</p>}
          </div>
          <PageHeaderAuth />
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-6 space-y-2">
        {book.sections && book.sections.length > 0 ? (
          <BookSectionsTree sections={book.sections} bookId={bookId} />
        ) : (
          <p className="text-center text-[#8C7A6B] py-12">אין תוכן בספר זה עדיין.</p>
        )}
      </main>
    </div>
  );
}
