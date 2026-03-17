'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { BookOpen, Loader2 } from 'lucide-react';
import { MarkdownRenderer } from '@/components/MarkdownRenderer';
import { Breadcrumb } from '@/components/Breadcrumb';
import { getCachedData, setCachedData } from '@/lib/cached-fetch';

export default function AboutPage() {
  const [about, setAbout] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const url = '/api/about';
    const cached = getCachedData(url);
    if (cached) {
      setAbout(cached);
      setIsLoading(false);
    }

    fetch(url)
      .then(res => res.json())
      .then(data => {
        setAbout(data);
        setCachedData(url, data);
        setIsLoading(false);
      })
      .catch(() => setIsLoading(false));
  }, []);

  if (isLoading) return <div className="min-h-screen bg-[#FAF8F5] flex items-center justify-center gap-3 text-[#8C7A6B] font-serif text-xl"><Loader2 size={24} className="animate-spin text-[#8C2B2B]" />טוען...</div>;

  const hasContent = about && (about.title || about.content);

  return (
    <div className="min-h-screen bg-[#FAF8F5] font-sans" dir="rtl">
      <header className="bg-white border-b border-[#E5E0D8] py-6 px-6">
        <div className="max-w-4xl mx-auto flex items-start gap-4">
          <Link href="/" className="p-2 rounded-full hover:bg-[#F0EBE1] transition-colors mt-1 shrink-0" title="חזרה לדף הראשי">
            <BookOpen size={28} className="text-[#8C2B2B]" />
          </Link>
          <div>
            <Breadcrumb items={[
              { label: 'ספרים', href: '/' },
              { label: 'אודות' },
            ]} />
            <h1 className="text-3xl font-serif font-bold text-[#4A3B32] mt-4">
              {about?.title || 'אודות'}
            </h1>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-8">
        {hasContent ? (
          <div className="bg-white p-6 sm:p-10 rounded-2xl shadow-sm border border-[#E5E0D8]">
            {about.imageUrl && (
              <div className="mb-8 rounded-xl overflow-hidden">
                <img
                  src={about.imageUrl}
                  alt={about.title || 'אודות'}
                  className="w-full max-h-[400px] object-cover"
                />
              </div>
            )}
            <div className="prose prose-lg max-w-none font-serif leading-loose text-[#2C2A29]">
              <MarkdownRenderer>{about.content}</MarkdownRenderer>
            </div>
          </div>
        ) : (
          <p className="text-center text-[#8C7A6B] py-12 text-lg">אין מידע עדיין.</p>
        )}
      </main>
    </div>
  );
}
