'use client';

import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import { SimpleMarkdown } from '@/components/MarkdownRenderer';

interface Announcement {
  id: string;
  title: string;
  content: string;
  createdAt: string;
}

export function AnnouncementsBanner({ initialAnnouncements }: { initialAnnouncements: Announcement[] }) {
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [show, setShow] = useState(false);

  useEffect(() => {
    // Analytics tracking (only client side)
    if (!sessionStorage.getItem('visited')) {
      fetch('/api/analytics', { method: 'POST' }).catch(console.error);
      sessionStorage.setItem('visited', 'true');
    }

    if (!initialAnnouncements || initialAnnouncements.length === 0) return;

    try {
      const readIds: string[] = JSON.parse(localStorage.getItem('readAnnouncements') || '[]');
      const unread = initialAnnouncements.filter(a => !readIds.includes(a.id));
      if (unread.length > 0) {
        setAnnouncements(unread);
        setShow(true);
      }
    } catch {
      // In case localStorage is blocked
    }
  }, [initialAnnouncements]);

  const dismissAnnouncement = (id: string) => {
    try {
      const readIds: string[] = JSON.parse(localStorage.getItem('readAnnouncements') || '[]');
      readIds.push(id);
      localStorage.setItem('readAnnouncements', JSON.stringify(readIds));
    } catch {}

    const remaining = announcements.filter(a => a.id !== id);
    setAnnouncements(remaining);
    if (remaining.length === 0) setShow(false);
  };

  if (!show || announcements.length === 0) return null;

  return (
    <div className="bg-[#B14F1C] text-[#F1E6D2]">
      <div className="max-w-5xl mx-auto px-6 py-4 space-y-3">
        {announcements.map(a => (
          <div key={a.id} className="relative flex items-start gap-4 border-r-4 border-[#E5C547] pr-4 pl-10">
            <span className="text-[#E5C547] mt-1.5 text-xs">●</span>
            <div className="flex-1">
              <h3 className="font-serif text-xl font-semibold leading-tight">{a.title}</h3>
              <div className="font-serif text-sm leading-relaxed mt-1 text-[#F1E6D2]/90">
                <SimpleMarkdown>{a.content}</SimpleMarkdown>
              </div>
              <span className="text-[11px] text-[#F1E6D2]/60 mt-1.5 block font-sans italic">
                {new Date(a.createdAt).toLocaleDateString('he-IL')}
              </span>
            </div>
            <button
              onClick={() => dismissAnnouncement(a.id)}
              className="absolute top-0 left-0 text-[#F1E6D2]/70 hover:text-[#E5C547] p-1 transition-colors"
              aria-label="סגור הודעה"
            >
              <X size={16} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
