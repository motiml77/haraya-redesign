import React from 'react';
import Link from 'next/link';
import { BookOpen, Info, Hash, Mail } from 'lucide-react';
import { adminDb } from '@/lib/firebase-admin';
import { getCached, setCache } from '@/lib/cache';
import { PageHeaderAuth } from '@/components/PageHeaderAuth';
import { AnnouncementsBanner } from '@/components/AnnouncementsBanner';

// ISR: serve static pages, revalidate in background every 30 seconds
export const revalidate = 30;

async function getBooks() {
  const cacheKey = 'books:list';
  const cached = getCached<any[]>(cacheKey);
  if (cached) return cached;

  try {
    const snapshot = await adminDb.collection('books').orderBy('orderIndex').get();
    const books = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
    setCache(cacheKey, books, 60_000);
    return books;
  } catch (error) {
    console.error('Error fetching books for SSR:', error);
    return [];
  }
}

async function getAnnouncements() {
  const cacheKey = 'announcements:all';
  const cached = getCached<any[]>(cacheKey);
  if (cached) return cached;

  try {
    const snapshot = await adminDb.collection('announcements')
      .where('type', '==', 'all')
      .get();

    const announcements = snapshot.docs
      .map(doc => ({ id: doc.id, ...doc.data() }))
      .sort((a: any, b: any) => {
        const aTime = a.createdAt?._seconds || a.createdAt?.seconds || 0;
        const bTime = b.createdAt?._seconds || b.createdAt?.seconds || 0;
        return bTime - aTime;
      })
      .slice(0, 20);
    setCache(cacheKey, announcements, 60_000);
    return announcements;
  } catch (error) {
    console.error('Error fetching announcements for SSR:', error);
    return [];
  }
}

export default async function HomePage() {
  const booksPromise = getBooks();
  const announcementsPromise = getAnnouncements();

  // Fetch in parallel
  const [books, announcements] = await Promise.all([booksPromise, announcementsPromise]);

  return (
    <div className="min-h-screen bg-[#FAF8F5] font-sans" dir="rtl">
      <header className="bg-white border-b border-[#E5E0D8] px-4 sm:px-6">
        {/* Row 1: Logo + Auth */}
        <div className="flex justify-between items-center py-3 border-b border-[#F0EBE1]">
          <div className="flex items-center gap-2">
            <BookOpen size={28} className="text-[#8C2B2B]" />
            <span className="text-lg font-serif font-bold text-[#8C2B2B]">ראשי</span>
          </div>
          <PageHeaderAuth />
        </div>
        {/* Row 2: Navigation buttons */}
        <div className="flex items-center justify-center gap-2 py-3">
          <Link href="/topics"
            className="flex items-center gap-0.5 text-xs text-[#8C7A6B] hover:text-[#8C2B2B] transition-colors px-3 py-1.5 rounded-full border border-[#E5E0D8] hover:border-[#8C2B2B] bg-[#FAF8F5]">
            <Hash size={14} />
            נושאים
          </Link>
          <Link href="/contact"
            className="flex items-center gap-1.5 text-xs text-[#8C7A6B] hover:text-[#8C2B2B] transition-colors px-3 py-1.5 rounded-full border border-[#E5E0D8] hover:border-[#8C2B2B] bg-[#FAF8F5]">
            <Mail size={14} />
            צור קשר
          </Link>
          <Link href="/about"
            className="flex items-center gap-1.5 text-xs text-[#8C7A6B] hover:text-[#8C2B2B] transition-colors px-3 py-1.5 rounded-full border border-[#E5E0D8] hover:border-[#8C2B2B] bg-[#FAF8F5]">
            <Info size={14} />
            אודות
          </Link>
        </div>
        {/* Title */}
        <div className="max-w-4xl mx-auto text-center py-8">
          <h1 className="text-3xl sm:text-4xl font-serif font-bold text-[#4A3B32]">שיעורים בכתבי הרב קוק</h1>
          <p className="text-[#8C7A6B] mt-3 text-base sm:text-lg">ביאורים והרחבות על כתבי מרן הרב אברהם יצחק הכהן קוק זצ״ל</p>
        </div>
      </header>

      <AnnouncementsBanner initialAnnouncements={announcements} />

      <main className="max-w-4xl mx-auto px-6 py-10">
        {books.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {books.filter((book: any) => !book.isHidden).map((book: any) => (
              <Link key={book.id} href={`/book/${book.id}`}
                className="bg-white p-6 rounded-2xl shadow-sm border border-[#E5E0D8] hover:border-[#8C2B2B] hover:shadow-md transition-all group">
                <div className="flex items-center gap-3 mb-3">
                  <BookOpen size={24} className="text-[#8C2B2B]" />
                  <h2 className="text-xl font-serif font-bold text-[#4A3B32] group-hover:text-[#8C2B2B] transition-colors">{book.title}</h2>
                </div>
                {book.description && <p className="text-sm text-[#8C7A6B] leading-relaxed">{book.description}</p>}
              </Link>
            ))}
          </div>
        ) : (
          <p className="text-center text-[#8C7A6B] py-12 text-lg">אין ספרים עדיין.</p>
        )}
      </main>
    </div>
  );
}
