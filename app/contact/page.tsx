'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { BookOpen, Send, CheckCircle, Loader2 } from 'lucide-react';
import { Breadcrumb } from '@/components/Breadcrumb';
import { PageHeaderAuth } from '@/components/PageHeaderAuth';

export default function ContactPage() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [isSent, setIsSent] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !message.trim()) {
      setError('שם והודעה הם שדות חובה');
      return;
    }

    setIsSending(true);
    setError('');

    try {
      const res = await fetch('/api/contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim(), email: email.trim(), subject: subject.trim(), message: message.trim() }),
      });
      const data = await res.json();
      if (data.success) {
        setIsSent(true);
      } else {
        setError(data.error || 'שגיאה בשליחה');
      }
    } catch {
      setError('שגיאה בשליחה, נסה שוב');
    } finally {
      setIsSending(false);
    }
  };

  const inputClass = "w-full p-3 border border-[#D6C8A8] bg-[#F1E6D2] focus:bg-white focus:border-[#B14F1C] focus:outline-none text-sm font-serif text-[#1F1A14]";

  return (
    <div className="min-h-screen bg-[#F1E6D2] font-sans" dir="rtl">
      {/* Top dark strip */}
      <div className="bg-[#1F1A14] text-[#F1E6D2] px-6 py-3 flex justify-between items-center">
        <Breadcrumb items={[
          { label: 'הראי״ה · ספרייה', href: '/' },
          { label: 'צור קשר' },
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
          ש
        </div>
        <div className="relative max-w-4xl mx-auto">
          <Link href="/" className="inline-flex items-center gap-2 text-xs text-[#6B5D4F] hover:text-[#B14F1C] mb-4 font-bold tracking-[0.2em]">
            <BookOpen size={14} className="text-[#B14F1C]" />
            ← חזרה לספרייה
          </Link>
          <div className="text-xs tracking-[0.3em] font-bold text-[#B14F1C] mb-3">● צור קשר</div>
          <h1 className="font-serif text-5xl sm:text-7xl font-semibold text-[#1F1A14] leading-[0.95] tracking-tight">
            נשמח לשמוע <span className="italic text-[#B14F1C]">ממך.</span>
          </h1>
          <p className="text-[#6B5D4F] mt-4 max-w-xl font-serif text-lg leading-relaxed">
            שאלות, הצעות, הערות, או כל פנייה אחרת — נחזור אליך בהקדם.
          </p>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-6 py-10">
        {isSent ? (
          <div className="bg-[#E8DCC4] p-10 sm:p-14 border border-[#D6C8A8] text-center">
            <div className="w-16 h-16 mx-auto mb-5 rounded-full bg-[#B14F1C] flex items-center justify-center">
              <CheckCircle size={32} className="text-[#F1E6D2]" />
            </div>
            <h2 className="text-3xl font-serif font-semibold text-[#1F1A14] mb-3">ההודעה נשלחה<span className="text-[#B14F1C]">.</span></h2>
            <p className="text-[#6B5D4F] mb-7 font-serif italic">תודה על פנייתך. נשתדל לחזור אליך בהקדם.</p>
            <Link href="/" className="inline-flex items-center gap-2 px-6 py-3 bg-[#1F1A14] text-[#F1E6D2] hover:bg-[#B14F1C] transition-colors font-bold tracking-wide text-sm">
              <BookOpen size={16} />
              חזרה לספרייה
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="bg-[#E8DCC4] p-6 sm:p-10 border border-[#D6C8A8] space-y-5">
            <div className="border-b border-[#D6C8A8] pb-4 mb-2">
              <div className="text-xs tracking-[0.25em] font-bold text-[#B14F1C] mb-1">● טופס פנייה</div>
              <h2 className="font-serif text-2xl text-[#1F1A14]">מלא את הפרטים</h2>
            </div>

            <div>
              <label className="block text-xs font-bold text-[#1F1A14] mb-1.5 tracking-wider uppercase">שם <span className="text-[#B14F1C]">*</span></label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className={inputClass}
                placeholder="השם שלך"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-[#1F1A14] mb-1.5 tracking-wider uppercase">אימייל <span className="text-[10px] text-[#6B5D4F] font-normal normal-case">(אופציונלי)</span></label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={inputClass}
                placeholder="your@email.com"
                dir="ltr"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-[#1F1A14] mb-1.5 tracking-wider uppercase">נושא</label>
              <input
                type="text"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                className={inputClass}
                placeholder="נושא הפנייה"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-[#1F1A14] mb-1.5 tracking-wider uppercase">הודעה <span className="text-[#B14F1C]">*</span></label>
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                className={`${inputClass} resize-none leading-relaxed`}
                rows={6}
                placeholder="כתוב את הודעתך כאן..."
              />
            </div>

            {error && (
              <div className="border-r-4 border-[#B14F1C] bg-[#F1E6D2] px-4 py-3">
                <p className="text-[#B14F1C] text-sm font-bold">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={isSending}
              className="w-full flex items-center justify-center gap-2 px-6 py-3.5 bg-[#1F1A14] text-[#F1E6D2] hover:bg-[#B14F1C] transition-colors font-bold disabled:opacity-60 tracking-wider text-sm"
            >
              {isSending ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
              {isSending ? 'שולח...' : 'שלח הודעה'}
            </button>
          </form>
        )}
      </main>
    </div>
  );
}
