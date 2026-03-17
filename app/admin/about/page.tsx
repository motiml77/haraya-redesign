'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Save, Eye, Loader2, Image } from 'lucide-react';
import { authFetch } from '@/lib/auth-fetch';
import { useAdminUser } from '../admin-context';
import { MarkdownToolbar } from '@/components/MarkdownToolbar';
import { MarkdownRenderer } from '@/components/MarkdownRenderer';

export default function AdminAboutPage() {
  const { user } = useAdminUser();
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [imageUrl, setImageUrl] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');
  const [showPreview, setShowPreview] = useState(false);

  const contentRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    fetch('/api/about')
      .then(res => res.json())
      .then(data => {
        if (data) {
          setTitle(data.title || '');
          setContent(data.content || '');
          setImageUrl(data.imageUrl || '');
        }
        setIsLoading(false);
      })
      .catch(() => setIsLoading(false));
  }, []);

  const handleSave = async () => {
    if (isSaving) return;
    setIsSaving(true);
    setSaveMessage('');

    try {
      const res = await authFetch('/api/about', {
        method: 'PUT',
        body: JSON.stringify({ title, content, imageUrl }),
      });
      const data = await res.json();
      if (data.success) {
        setSaveMessage('נשמר בהצלחה!');
      } else {
        setSaveMessage(data.error || 'שגיאה בשמירה');
      }
    } catch {
      setSaveMessage('שגיאה בשמירה');
    }
    setIsSaving(false);
    setTimeout(() => setSaveMessage(''), 3000);
  };

  if (user?.role !== 'admin') {
    return (
      <div className="text-center py-12 text-[#8C7A6B]">
        <p className="text-xl font-serif">אין לך הרשאה לערוך דף זה</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12 gap-3 text-[#8C7A6B]">
        <Loader2 size={24} className="animate-spin text-[#8C2B2B]" />
        <span className="font-serif text-xl">טוען...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-serif font-bold text-[#4A3B32]">עריכת דף אודות</h2>
        <div className="flex items-center gap-3">
          {saveMessage && (
            <span className={`text-sm font-bold ${saveMessage.includes('בהצלחה') ? 'text-green-600' : 'text-red-600'}`}>
              {saveMessage}
            </span>
          )}
          <button
            onClick={() => setShowPreview(!showPreview)}
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold bg-[#F0EBE1] text-[#4A3B32] hover:bg-[#E5E0D8] transition-colors"
          >
            <Eye size={18} />
            {showPreview ? 'חזרה לעריכה' : 'תצוגה מקדימה'}
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="flex items-center gap-2 px-5 py-2 rounded-xl text-sm font-bold bg-[#8C2B2B] text-white hover:bg-[#7A2525] transition-colors disabled:opacity-50"
          >
            {isSaving ? <Loader2 size={18} className="animate-spin" /> : <Save size={18} />}
            {isSaving ? 'שומר...' : 'שמור'}
          </button>
        </div>
      </div>

      {showPreview ? (
        /* Live Preview */
        <div className="bg-white p-8 rounded-2xl shadow-sm border border-[#E5E0D8]">
          <h1 className="text-3xl font-serif font-bold text-[#4A3B32] mb-6">{title || 'אודות'}</h1>
          {imageUrl && (
            <div className="mb-8 rounded-xl overflow-hidden">
              <img src={imageUrl} alt={title} className="w-full max-h-[400px] object-cover" />
            </div>
          )}
          <div className="prose prose-lg max-w-none font-serif leading-loose text-[#2C2A29]">
            <MarkdownRenderer>{content}</MarkdownRenderer>
          </div>
        </div>
      ) : (
        /* Editor */
        <div className="space-y-6">
          {/* Title */}
          <div className="bg-white p-6 rounded-2xl shadow-sm border border-[#E5E0D8]">
            <label className="block text-sm font-bold text-[#8C7A6B] mb-2">כותרת הדף</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full p-3 rounded-xl border border-[#E5E0D8] bg-[#FAF8F5] focus:ring-2 focus:ring-[#8C2B2B] outline-none text-lg"
              placeholder="אודות האתר"
            />
          </div>

          {/* Image URL */}
          <div className="bg-white p-6 rounded-2xl shadow-sm border border-[#E5E0D8]">
            <label className="block text-sm font-bold text-[#8C7A6B] mb-2 flex items-center gap-2">
              <Image size={16} />
              קישור לתמונה (URL)
            </label>
            <input
              type="url"
              value={imageUrl}
              onChange={(e) => setImageUrl(e.target.value)}
              className="w-full p-3 rounded-xl border border-[#E5E0D8] bg-[#FAF8F5] focus:ring-2 focus:ring-[#8C2B2B] outline-none"
              placeholder="https://example.com/image.jpg"
              dir="ltr"
            />
            {imageUrl && (
              <div className="mt-4 rounded-xl overflow-hidden border border-[#E5E0D8]">
                <img
                  src={imageUrl}
                  alt="תצוגה מקדימה"
                  className="w-full max-h-[200px] object-cover"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = 'none';
                  }}
                />
              </div>
            )}
          </div>

          {/* Content */}
          <div className="bg-white rounded-2xl shadow-sm border border-[#E5E0D8] overflow-hidden">
            <div className="p-6 pb-0">
              <label className="block text-sm font-bold text-[#8C7A6B] mb-2">תוכן הדף</label>
            </div>
            <div className="px-6 pb-6">
              <MarkdownToolbar textareaRef={contentRef} />
              <textarea
                ref={contentRef}
                value={content}
                onChange={(e) => setContent(e.target.value)}
                className="w-full p-4 rounded-b-xl border border-[#E5E0D8] border-t-0 bg-[#FAF8F5] focus:ring-2 focus:ring-[#8C2B2B] outline-none resize-none font-serif leading-relaxed min-h-[400px]"
                placeholder="כתוב כאן את תוכן דף האודות... ניתן להשתמש בעיצוב Markdown"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
