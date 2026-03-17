'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { BookOpen, Send, CheckCircle, Loader2 } from 'lucide-react';
import { Breadcrumb } from '@/components/Breadcrumb';

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
              { label: 'צור קשר' },
            ]} />
            <h1 className="text-3xl font-serif font-bold text-[#4A3B32] mt-4">צור קשר</h1>
            <p className="text-[#8C7A6B] mt-2">נשמח לשמוע ממך — שאלות, הצעות, הערות או כל פנייה אחרת</p>
          </div>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-6 py-8">
        {isSent ? (
          <div className="bg-white p-8 sm:p-12 rounded-2xl shadow-sm border border-[#E5E0D8] text-center">
            <CheckCircle size={48} className="text-green-600 mx-auto mb-4" />
            <h2 className="text-2xl font-serif font-bold text-[#4A3B32] mb-3">ההודעה נשלחה בהצלחה!</h2>
            <p className="text-[#8C7A6B] mb-6">תודה על פנייתך. נשתדל לחזור אליך בהקדם.</p>
            <Link href="/" className="inline-flex items-center gap-2 px-6 py-3 bg-[#8C2B2B] text-white rounded-xl hover:bg-[#7A2525] transition-colors font-bold">
              <BookOpen size={18} />
              חזרה לדף הראשי
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="bg-white p-6 sm:p-10 rounded-2xl shadow-sm border border-[#E5E0D8] space-y-5">
            <div>
              <label className="block text-sm font-bold text-[#4A3B32] mb-1.5">שם <span className="text-[#8C2B2B]">*</span></label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full p-3 rounded-xl border border-[#E5E0D8] bg-[#FAF8F5] focus:ring-2 focus:ring-[#8C2B2B] focus:border-transparent outline-none text-sm"
                placeholder="השם שלך"
              />
            </div>

            <div>
              <label className="block text-sm font-bold text-[#4A3B32] mb-1.5">אימייל <span className="text-xs text-[#8C7A6B] font-normal">(אופציונלי)</span></label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full p-3 rounded-xl border border-[#E5E0D8] bg-[#FAF8F5] focus:ring-2 focus:ring-[#8C2B2B] focus:border-transparent outline-none text-sm"
                placeholder="your@email.com"
                dir="ltr"
              />
            </div>

            <div>
              <label className="block text-sm font-bold text-[#4A3B32] mb-1.5">נושא</label>
              <input
                type="text"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                className="w-full p-3 rounded-xl border border-[#E5E0D8] bg-[#FAF8F5] focus:ring-2 focus:ring-[#8C2B2B] focus:border-transparent outline-none text-sm"
                placeholder="נושא הפנייה"
              />
            </div>

            <div>
              <label className="block text-sm font-bold text-[#4A3B32] mb-1.5">הודעה <span className="text-[#8C2B2B]">*</span></label>
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                className="w-full p-3 rounded-xl border border-[#E5E0D8] bg-[#FAF8F5] focus:ring-2 focus:ring-[#8C2B2B] focus:border-transparent outline-none resize-none text-sm"
                rows={6}
                placeholder="כתוב את הודעתך כאן..."
              />
            </div>

            {error && (
              <p className="text-[#8C2B2B] text-sm font-bold">{error}</p>
            )}

            <button
              type="submit"
              disabled={isSending}
              className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-[#8C2B2B] text-white rounded-xl hover:bg-[#7A2525] transition-colors font-bold disabled:opacity-60"
            >
              {isSending ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
              {isSending ? 'שולח...' : 'שלח הודעה'}
            </button>
          </form>
        )}
      </main>
    </div>
  );
}
