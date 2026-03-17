'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { Hash, ChevronDown, BookOpen, ArrowRight } from 'lucide-react';
import { BookLoader } from '@/components/BookLoader';
import { getCachedData, setCachedData } from '@/lib/cached-fetch';

interface TagData {
  tag: string;
  count: number;
  sections: { id: string; title: string; bookTitle: string; bookId: string }[];
}

export default function TopicsPage() {
  const [tags, setTags] = useState<TagData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [expandedTag, setExpandedTag] = useState<string | null>(null);

  useEffect(() => {
    const cached = getCachedData<TagData[]>('/api/tags');
    if (cached && Array.isArray(cached)) {
      setTags(cached);
      setIsLoading(false);
    }

    fetch('/api/tags')
      .then(r => r.json())
      .then(data => {
        if (Array.isArray(data)) {
          setTags(data);
          setCachedData('/api/tags', data);
        }
        setIsLoading(false);
      })
      .catch(() => setIsLoading(false));
  }, []);

  if (isLoading) return <div className="min-h-screen bg-[#FAF8F5] flex items-center justify-center"><BookLoader text="טוען נושאים..." /></div>;

  return (
    <div className="min-h-screen bg-[#FAF8F5] font-sans" dir="rtl">
      <header className="bg-white border-b border-[#E5E0D8] py-6 px-6">
        <div className="max-w-4xl mx-auto">
          <Link href="/" className="inline-flex items-center gap-2 text-sm text-[#8C7A6B] hover:text-[#8C2B2B] transition-colors mb-4">
            <ArrowRight size={16} /> חזרה לדף הראשי
          </Link>
          <h1 className="text-3xl font-serif font-bold text-[#4A3B32] flex items-center gap-3">
            <Hash size={28} className="text-[#8C2B2B]" />
            נושאים ({tags.length})
          </h1>
          <p className="text-[#8C7A6B] mt-2">עיון לפי נושאים בכתבי הרב קוק</p>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-8">
        {tags.length === 0 ? (
          <p className="text-center text-[#8C7A6B] py-12 text-lg">אין נושאים עדיין.</p>
        ) : (
          <div className="grid grid-cols-1 gap-3">
            {tags.map(({ tag, count, sections }) => (
              <div key={tag} className="bg-white rounded-2xl shadow-sm border border-[#E5E0D8] overflow-hidden">
                <button onClick={() => setExpandedTag(expandedTag === tag ? null : tag)}
                  className="w-full flex justify-between items-center p-4 hover:bg-[#FAF8F5] transition-colors text-right">
                  <div className="flex items-center gap-3">
                    <span className="text-[#8C2B2B] font-bold text-lg">#</span>
                    <span className="font-bold text-[#4A3B32] text-lg">{tag}</span>
                    <span className="text-xs text-[#8C7A6B] bg-[#F0EBE1] px-2 py-0.5 rounded-full">{count} חלקים</span>
                  </div>
                  <ChevronDown size={20} className={`text-[#8C7A6B] transition-transform ${expandedTag === tag ? 'rotate-180' : ''}`} />
                </button>

                {expandedTag === tag && (
                  <div className="border-t border-[#E5E0D8] p-4 bg-[#FAF8F5] space-y-2">
                    {sections.map(s => (
                      <Link key={s.id} href={`/book/${s.bookId}/${s.id}`}
                        className="flex items-center gap-3 p-3 bg-white rounded-xl border border-[#E5E0D8] hover:border-[#8C2B2B] transition-colors group">
                        <BookOpen size={16} className="text-[#8C7A6B] group-hover:text-[#8C2B2B] shrink-0" />
                        <div className="flex-1 min-w-0">
                          <span className="text-sm font-bold text-[#4A3B32] block truncate">{s.title}</span>
                          <span className="text-xs text-[#8C7A6B]">{s.bookTitle}</span>
                        </div>
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
