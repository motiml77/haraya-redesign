import React from 'react';
import Link from 'next/link';
import { BookOpen } from 'lucide-react';
import { adminDb } from '@/lib/firebase-admin';
import { getCached, setCache } from '@/lib/cache';
import { Breadcrumb } from '@/components/Breadcrumb';
import { PageHeaderAuth } from '@/components/PageHeaderAuth';
import { BookSectionsTree } from '@/components/BookSectionsTree';

// ISR: serve static pages, revalidate in background every 30 seconds
export const revalidate = 30;

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

  if (!book) return <div className="min-h-screen bg-[#F1E6D2] flex items-center justify-center text-[#B14F1C] font-serif text-xl" suppressHydrationWarning>ספר לא נמצא</div>;

  return (
    <div className="min-h-screen bg-[#F1E6D2] font-sans" dir="rtl">
      {/* Top bar */}
      <div className="bg-[#1F1A14] text-[#F1E6D2] px-6 py-3 flex justify-between items-center">
        <div className="flex items-center gap-4 text-xs tracking-[0.2em] font-bold">
          <span className="text-[#E5C547]">●</span>
          <Link href="/" className="hover:text-[#E5C547] transition-colors">הראי״ה · ספרייה חיה</Link>
        </div>
        <PageHeaderAuth />
      </div>

      {/* Book header */}
      <header className="bg-[#B14F1C] text-[#F1E6D2] px-6 py-10">
        <div className="max-w-4xl mx-auto">
          <Breadcrumb items={[{ label: 'ספרים', href: '/' }, { label: book.title }]} />
          <h1 className="font-serif text-4xl sm:text-5xl font-semibold leading-tight tracking-tight mt-4">
            {book.title}<span className="text-[#E5C547]">.</span>
          </h1>
          {book.description && (
            <p className="font-serif italic text-lg mt-3 text-[#F1E6D2]/80">{book.description}</p>
          )}
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-8 space-y-2">
        {book.sections && book.sections.length > 0 ? (
          <BookSectionsTree sections={book.sections} bookId={bookId} />
        ) : (
          <p className="text-center text-[#6B5D4F] py-12 font-serif italic">אין תוכן בספר זה עדיין.</p>
        )}
      </main>

      <footer className="bg-[#1F1A14] text-[#F1E6D2] mt-20 px-6 py-8">
        <div className="max-w-4xl mx-auto flex justify-between items-center">
          <div className="font-serif text-sm text-[#F1E6D2]/60 italic">הראי״ה · ספרייה חיה</div>
          <Link href="/" className="text-xs text-[#E5C547] hover:underline tracking-wider">חזרה לדף הראשי ←</Link>
        </div>
      </footer>
    </div>
  );
}
