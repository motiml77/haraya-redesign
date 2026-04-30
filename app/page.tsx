import React from 'react';
import Link from 'next/link';
import Image from 'next/image';
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
  const [books, announcements] = await Promise.all([getBooks(), getAnnouncements()]);

  return (
    <div className="min-h-screen bg-[#F1E6D2] font-sans" dir="rtl">
      {/* Top bar — dark chrome */}
      <div className="bg-[#1F1A14] text-[#F1E6D2] px-6 py-3 flex justify-between items-center">
        <div className="flex items-center gap-4 text-xs tracking-[0.2em] font-bold">
          <span className="text-[#E5C547]">●</span>
          <span>הראי״ה · בית מדרש חי</span>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/topics"
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border border-[#6B5D4F] hover:border-[#E5C547] hover:text-[#E5C547] transition-colors">
            <Hash size={13} />
            נושאים
          </Link>
          <Link href="/contact"
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border border-[#6B5D4F] hover:border-[#E5C547] hover:text-[#E5C547] transition-colors">
            <Mail size={13} />
            צור קשר
          </Link>
          <Link href="/about"
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border border-[#6B5D4F] hover:border-[#E5C547] hover:text-[#E5C547] transition-colors">
            <Info size={13} />
            אודות
          </Link>
          <PageHeaderAuth />
        </div>
      </div>

      {/* Hero — manuscript style */}
      <header className="relative overflow-hidden bg-[#B14F1C] text-[#F1E6D2] px-6 sm:px-12 py-16 sm:py-24">
        {/* Giant decorative letter */}
        <div
          aria-hidden="true"
          className="ms-ornament absolute top-[-80px] right-[-40px] text-[420px] sm:text-[560px] opacity-[0.18]"
          style={{ fontFamily: 'var(--font-serif)' }}
        >
          ה
        </div>

        <div className="relative max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-[1fr_auto] gap-10 items-center">
          <div>
            <div className="text-xs tracking-[0.3em] font-bold text-[#E5C547] mb-4">● בית מדרש פתוח</div>
            <h1 className="font-serif text-5xl sm:text-7xl font-semibold leading-[0.95] tracking-tight">
              שיעורים בכתבי
              <br />
              <span className="italic">הרב קוק.</span>
            </h1>
            <p className="font-serif italic text-lg sm:text-xl mt-6 text-[#F1E6D2]/85 max-w-xl leading-relaxed">
              ביאורים והרחבות על כתבי מרן הרב אברהם יצחק הכהן קוק זצ״ל
            </p>
          </div>

          <div className="w-44 h-56 sm:w-52 sm:h-64 overflow-hidden border-[6px] border-[#F1E6D2] shadow-[0_20px_60px_rgba(0,0,0,0.3)] rotate-[-2deg] bg-[#F1E6D2]">
            <Image
              src="/rav-kook.webp"
              alt="הרב אברהם יצחק הכהן קוק זצ״ל"
              width={394}
              height={500}
              className="w-full h-full object-cover"
              priority
            />
          </div>
        </div>
      </header>

      <AnnouncementsBanner initialAnnouncements={announcements} />

      <main className="max-w-5xl mx-auto px-6 py-16">
        {/* Section header */}
        <div className="mb-10">
          <div className="text-xs tracking-[0.3em] font-bold text-[#B14F1C] mb-2">● הספרייה</div>
          <h2 className="font-serif text-4xl sm:text-5xl font-semibold text-[#1F1A14] tracking-tight">
            ספרים <span className="italic text-[#B14F1C]">לעיון.</span>
          </h2>
        </div>

        {books.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {books.filter((book: any) => !book.isHidden).map((book: any) => (
              <Link key={book.id} href={`/book/${book.id}`}
                className="group relative bg-[#E8DCC4] p-7 border border-[#D6C8A8] hover:border-[#B14F1C] hover:bg-[#F1E6D2] transition-all overflow-hidden">
                <div
                  aria-hidden="true"
                  className="absolute -bottom-6 -left-2 font-serif font-bold text-[120px] leading-[0.7] text-[#B14F1C]/[0.08] group-hover:text-[#B14F1C]/[0.18] transition-colors pointer-events-none select-none"
                >
                  {book.title?.[0] || 'א'}
                </div>
                <div className="relative">
                  <BookOpen size={20} className="text-[#B14F1C] mb-3" />
                  <h3 className="font-serif text-2xl font-semibold text-[#1F1A14] leading-tight group-hover:text-[#B14F1C] transition-colors">
                    {book.title}
                  </h3>
                  {book.description && (
                    <p className="font-serif italic text-sm text-[#6B5D4F] leading-relaxed mt-3">
                      {book.description}
                    </p>
                  )}
                  <div className="mt-5 pt-4 border-t border-dashed border-[#D6C8A8] text-xs text-[#B14F1C] font-bold tracking-wider">
                    קרא ←
                  </div>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <p className="text-center text-[#6B5D4F] py-12 text-lg font-serif italic">אין ספרים עדיין.</p>
        )}
      </main>

      {/* Footer */}
      <footer className="bg-[#1F1A14] text-[#F1E6D2] mt-20 px-6 py-12">
        <div className="max-w-5xl mx-auto flex flex-col sm:flex-row justify-between items-start gap-6">
          <div>
            <div className="text-xs tracking-[0.3em] font-bold text-[#E5C547]">● הראי״ה</div>
            <div className="font-serif text-2xl font-semibold mt-1">בית מדרש חי</div>
            <div className="font-serif italic text-sm text-[#F1E6D2]/60 mt-2">
              ביאורים והרחבות על כתבי מרן הרב קוק זצ״ל
            </div>
          </div>
          <div className="flex gap-6 text-sm">
            <Link href="/about" className="hover:text-[#E5C547] transition-colors">אודות</Link>
            <Link href="/contact" className="hover:text-[#E5C547] transition-colors">צור קשר</Link>
            <Link href="/topics" className="hover:text-[#E5C547] transition-colors">נושאים</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
