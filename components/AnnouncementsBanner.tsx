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
    <div className="max-w-4xl mx-auto px-6 pt-6">
      <div className="space-y-3">
        {announcements.map(a => (
          <div key={a.id} className="bg-white p-4 rounded-2xl shadow-sm border border-[#E5E0D8] relative">
            <button onClick={() => dismissAnnouncement(a.id)} className="absolute top-3 left-3 text-[#8C7A6B] hover:text-[#8C2B2B] p-1 transition-colors">
              <X size={16} />
            </button>
            <h3 className="font-bold text-[#4A3B32] mb-2">{a.title}</h3>
            <div className="text-sm text-[#4A3B32] leading-relaxed">
              <SimpleMarkdown>{a.content}</SimpleMarkdown>
            </div>
            <span className="text-xs text-[#8C7A6B] mt-2 block">{new Date(a.createdAt).toLocaleDateString('he-IL')}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
