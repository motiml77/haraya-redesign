'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { BookOpen, Loader2 } from 'lucide-react';
import { MarkdownRenderer } from '@/components/MarkdownRenderer';
import { Breadcrumb } from '@/components/Breadcrumb';
import { PageHeaderAuth } from '@/components/PageHeaderAuth';
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

  if (isLoading) return <div className="min-h-screen bg-[#F1E6D2] flex items-center justify-center gap-3 text-[#6B5D4F] font-serif text-xl"><Loader2 size={24} className="animate-spin text-[#B14F1C]" />טוען...</div>;

  const hasContent = about && (about.title || about.content);

  return (
    <div className="min-h-screen bg-[#F1E6D2] font-sans" dir="rtl">
      {/* Top dark strip */}
      <div className="bg-[#1F1A14] text-[#F1E6D2] px-6 py-3 flex justify-between items-center">
        <Breadcrumb items={[
          { label: 'הראי״ה · ספרייה', href: '/' },
          { label: 'אודות' },
        ]} />
        <PageHeaderAuth />
      </div>

      {/* Hero */}
      <header className="relative overflow-hidden bg-[#E8DCC4] px-6 sm:px-12 py-14 border-b-2 border-[#D6C8A8]">
        <div
          aria-hidden="true"
          className="ms-ornament absolute -top-12 -left-6 text-[280px] sm:text-[400px] text-[#B14F1C]/[0.08]"
          style={{ fontFamily: 'var(--font-serif)' }}
        >
          א
        </div>
        <div className="relative max-w-4xl mx-auto">
          <Link href="/" className="inline-flex items-center gap-2 text-xs text-[#6B5D4F] hover:text-[#B14F1C] mb-4 font-bold tracking-[0.2em]">
            <BookOpen size={14} className="text-[#B14F1C]" />
            ← חזרה לספרייה
          </Link>
          <div className="text-xs tracking-[0.3em] font-bold text-[#B14F1C] mb-3">● אודות</div>
          <h1 className="font-serif text-5xl sm:text-7xl font-semibold text-[#1F1A14] leading-[0.95] tracking-tight">
            {about?.title ? <>{about.title}<span className="text-[#B14F1C]">.</span></> : <>על <span className="italic text-[#B14F1C]">הספרייה.</span></>}
          </h1>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-14">
        {hasContent ? (
          <div className="bg-[#E8DCC4] p-8 sm:p-12 border border-[#D6C8A8] relative">
            {about.imageUrl && (
              <div className="mb-8 overflow-hidden border-[5px] border-[#F1E6D2]">
                <img
                  src={about.imageUrl}
                  alt={about.title || 'אודות'}
                  className="w-full max-h-[400px] object-cover"
                />
              </div>
            )}
            <div className="prose prose-lg max-w-none font-serif leading-loose text-[#1F1A14] prose-headings:text-[#B14F1C] prose-headings:font-semibold prose-a:text-[#B14F1C] prose-strong:text-[#1F1A14] prose-em:text-[#6B5D4F]">
              <MarkdownRenderer>{about.content}</MarkdownRenderer>
            </div>
          </div>
        ) : (
          <p className="text-center text-[#6B5D4F] py-12 text-lg font-serif italic">אין מידע עדיין.</p>
        )}
      </main>
    </div>
  );
}
