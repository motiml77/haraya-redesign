'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { Hash, ChevronDown, BookOpen, Loader2 } from 'lucide-react';
import { Breadcrumb } from '@/components/Breadcrumb';
import { PageHeaderAuth } from '@/components/PageHeaderAuth';
import { getCachedData, setCachedData } from '@/lib/cached-fetch';

interface TagData {
  tag: string;
  count: number;
  sections: { id: string; title: string; bookTitle: string; bookId?: string }[];
}

export default function TopicsPage() {
  const [tags, setTags] = useState<TagData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [expandedTag, setExpandedTag] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    const url = '/api/tags';
    const cached = getCachedData<TagData[]>(url);
    if (cached) {
      setTags(cached);
      setIsLoading(false);
    }
    fetch(url)
      .then(r => r.json())
      .then(data => {
        if (Array.isArray(data)) {
          setTags(data);
          setCachedData(url, data);
        }
        setIsLoading(false);
      })
      .catch(() => setIsLoading(false));
  }, []);

  const filteredTags = searchQuery.trim()
    ? tags.filter(t => t.tag.toLowerCase().includes(searchQuery.toLowerCase()))
    : tags;

  // Sort by count desc for visual rhythm
  const sortedTags = [...filteredTags].sort((a, b) => b.count - a.count);

  return (
    <div className="min-h-screen bg-[#F1E6D2] font-sans" dir="rtl">
      {/* Top dark strip */}
      <div className="bg-[#1F1A14] text-[#F1E6D2] px-6 py-3 flex justify-between items-center">
        <Breadcrumb items={[
          { label: 'הראי״ה · ספרייה', href: '/' },
          { label: 'נושאים' },
        ]} />
        <PageHeaderAuth />
      </div>

      {/* Hero */}
      <header className="relative overflow-hidden bg-[#E8DCC4] px-6 sm:px-12 py-14 border-b-2 border-[#D6C8A8]">
        <div
          aria-hidden="true"
          className="absolute -top-12 -left-6 text-[280px] sm:text-[400px] text-[#B14F1C]/[0.08] leading-none select-none"
          style={{ fontFamily: 'var(--font-serif)' }}
        >
          ת
        </div>
        <div className="relative max-w-5xl mx-auto">
          <Link href="/" className="inline-flex items-center gap-2 text-xs text-[#6B5D4F] hover:text-[#B14F1C] mb-4 font-bold tracking-[0.2em]">
            <BookOpen size={14} className="text-[#B14F1C]" />
            ← חזרה לספרייה
          </Link>
          <div className="text-xs tracking-[0.3em] font-bold text-[#B14F1C] mb-3">● אינדקס</div>
          <h1 className="font-serif text-5xl sm:text-7xl font-semibold text-[#1F1A14] leading-[0.95] tracking-tight">
            נושאים <span className="italic text-[#B14F1C]">ותגיות.</span>
          </h1>
          <p className="font-serif italic text-lg text-[#6B5D4F] mt-5 max-w-2xl leading-relaxed">
            אינדקס נושאי של פסקאות מצולבות לאורך כל הספרים. לחץ על נושא כדי לראות את כל המקומות שבהם הוא מופיע.
          </p>

          {/* Search */}
          <div className="mt-8 max-w-md">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="סנן לפי שם נושא..."
              className="w-full p-3 border border-[#D6C8A8] bg-[#F1E6D2] focus:bg-white focus:border-[#B14F1C] focus:outline-none text-sm font-serif text-[#1F1A14] placeholder:text-[#6B5D4F]/60"
            />
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-12">
        {isLoading ? (
          <div className="flex items-center justify-center gap-3 text-[#6B5D4F] font-serif italic py-20">
            <Loader2 size={20} className="animate-spin text-[#B14F1C]" />
            טוען נושאים...
          </div>
        ) : sortedTags.length === 0 ? (
          <div className="text-center py-20">
            <p className="text-[#6B5D4F] font-serif italic text-lg">
              {searchQuery ? 'לא נמצאו נושאים תואמים.' : 'אין נושאים עדיין.'}
            </p>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between mb-6 pb-4 border-b border-[#D6C8A8]">
              <div>
                <div className="text-xs tracking-[0.3em] font-bold text-[#B14F1C] mb-1">● {sortedTags.length} נושאים</div>
                <h2 className="font-serif text-2xl text-[#1F1A14]">לפי שכיחות.</h2>
              </div>
            </div>

            <div className="space-y-2">
              {sortedTags.map(({ tag, count, sections }) => {
                const isOpen = expandedTag === tag;
                return (
                  <div key={tag} className="bg-[#E8DCC4] border border-[#D6C8A8] overflow-hidden">
                    <button
                      onClick={() => setExpandedTag(isOpen ? null : tag)}
                      className={`w-full flex justify-between items-center px-5 py-4 hover:bg-[#F1E6D2] transition-colors text-right ${isOpen ? 'bg-[#F1E6D2]' : ''}`}
                    >
                      <div className="flex items-center gap-4 min-w-0">
                        <span className="text-[#B14F1C] font-serif text-3xl font-semibold leading-none">#</span>
                        <span className="font-serif text-xl text-[#1F1A14] truncate">{tag}</span>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <span className="text-xs text-[#6B5D4F] tracking-wider uppercase font-bold">
                          {count} {count === 1 ? 'פסקה' : 'פסקאות'}
                        </span>
                        <ChevronDown
                          size={18}
                          className={`text-[#6B5D4F] transition-transform ${isOpen ? 'rotate-180 text-[#B14F1C]' : ''}`}
                        />
                      </div>
                    </button>

                    {isOpen && (
                      <div className="border-t border-[#D6C8A8] bg-[#F4E3C7]/40 p-4 space-y-1.5">
                        {sections.map((s) => (
                          <Link
                            key={s.id}
                            href={s.bookId ? `/book/${s.bookId}/${s.id}` : `/admin/sections/${s.id}`}
                            className="flex items-center gap-3 p-3 bg-[#E8DCC4] border border-[#D6C8A8] hover:border-[#B14F1C] hover:bg-[#F1E6D2] transition-colors group"
                          >
                            <BookOpen size={14} className="text-[#6B5D4F] group-hover:text-[#B14F1C] shrink-0" />
                            <div className="flex-1 min-w-0">
                              <div className="font-serif text-[#1F1A14] truncate group-hover:text-[#B14F1C] transition-colors">
                                {s.title}
                              </div>
                              <div className="text-xs text-[#6B5D4F] mt-0.5 italic">{s.bookTitle}</div>
                            </div>
                            <span className="text-[#B14F1C] opacity-0 group-hover:opacity-100 transition-opacity text-sm">
                              ←
                            </span>
                          </Link>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
