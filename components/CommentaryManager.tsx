'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Pencil, Trash2, Plus, Check, X, Loader2 } from 'lucide-react';
import { SimpleMarkdown } from '@/components/MarkdownRenderer';
import { MarkdownToolbar } from '@/components/MarkdownToolbar';
import { useWordPasteHandler } from '@/hooks/use-word-paste';

interface CommentarySection {
  id: string;
  text: string;
}

interface CommentaryManagerProps {
  commentaries: CommentarySection[];
  canEdit: boolean;
  onSave: (updated: CommentarySection[]) => Promise<void>;
  isBookMode: boolean;
  bookContainerRef?: React.RefObject<HTMLDivElement | null>;
}

export function CommentaryManager({ commentaries, canEdit, onSave, isBookMode, bookContainerRef }: CommentaryManagerProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useWordPasteHandler(textareaRef, setEditValue, () => editValue);

  useEffect(() => {
    if (editingId && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [editingId]);

  const startEdit = (section: CommentarySection) => {
    setEditingId(section.id);
    setEditValue(section.text);
    setMessage('');
  };

  const handleSave = async () => {
    if (isSaving) return;
    setIsSaving(true);
    setMessage('');
    try {
      const updated = commentaries.map(s =>
        s.id === editingId ? { ...s, text: editValue } : s
      );
      await onSave(updated);
      setEditingId(null);
      setMessage('נשמר!');
      setTimeout(() => setMessage(''), 2000);
    } catch {
      setMessage('שגיאה בשמירה');
      setTimeout(() => setMessage(''), 3000);
    }
    setIsSaving(false);
  };

  const handleCancel = () => {
    setEditingId(null);
    setEditValue('');
    setMessage('');
  };

  const handleDelete = async (id: string) => {
    if (!confirm('למחוק קטע ביאור זה?')) return;
    setIsSaving(true);
    try {
      const updated = commentaries.filter(s => s.id !== id);
      await onSave(updated);
      setMessage('נמחק!');
      setTimeout(() => setMessage(''), 2000);
    } catch {
      setMessage('שגיאה במחיקה');
      setTimeout(() => setMessage(''), 3000);
    }
    setIsSaving(false);
  };

  const handleAdd = async () => {
    setIsSaving(true);
    try {
      const newSection: CommentarySection = {
        id: `s${Date.now()}`,
        text: '',
      };
      const updated = [...commentaries, newSection];
      await onSave(updated);
      setEditingId(newSection.id);
      setEditValue('');
      setMessage('');
    } catch {
      setMessage('שגיאה בהוספה');
      setTimeout(() => setMessage(''), 3000);
    }
    setIsSaving(false);
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setEditValue(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = e.target.scrollHeight + 'px';
  };

  const renderSection = (section: CommentarySection) => {
    const isEditingThis = editingId === section.id;

    if (isEditingThis) {
      return (
        <div key={section.id} className="mb-6">
          <MarkdownToolbar textareaRef={textareaRef} />
          <textarea
            ref={textareaRef}
            value={editValue}
            onChange={handleInput}
            className="w-full p-4 rounded-b-xl border border-[#E5E0D8] border-t-0 bg-[#FAF8F5] focus:ring-2 focus:ring-[#8C2B2B] outline-none resize-none font-serif leading-relaxed min-h-[120px]"
          />
          <div className="flex items-center gap-2 mt-3">
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-bold bg-[#8C2B2B] text-white hover:bg-[#7A2525] transition-colors disabled:opacity-50"
            >
              {isSaving ? <Loader2 size={16} className="animate-spin" /> : <Check size={16} />}
              {isSaving ? 'שומר...' : 'שמור'}
            </button>
            <button
              onClick={handleCancel}
              disabled={isSaving}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-bold bg-[#F0EBE1] text-[#4A3B32] hover:bg-[#E5E0D8] transition-colors"
            >
              <X size={16} />
              ביטול
            </button>
          </div>
        </div>
      );
    }

    return (
      <div key={section.id} className="mb-6">
        <div className="text-base leading-relaxed text-[#4A3B32] text-justify">
          <SimpleMarkdown>{section.text || ''}</SimpleMarkdown>
        </div>
        {canEdit && (
          <div className="flex gap-1 mt-2">
            <button
              onClick={() => startEdit(section)}
              className="flex items-center gap-1 px-2.5 py-1 rounded-lg border border-[#E5E0D8] text-[#8C7A6B] hover:text-[#8C2B2B] hover:border-[#8C2B2B] transition-all text-xs font-bold"
              title="ערוך"
            >
              <Pencil size={12} />
              ערוך
            </button>
            <button
              onClick={() => handleDelete(section.id)}
              className="flex items-center gap-1 px-2.5 py-1 rounded-lg border border-[#E5E0D8] text-[#8C7A6B] hover:text-red-600 hover:border-red-400 transition-all text-xs font-bold"
              title="מחק"
            >
              <Trash2 size={12} />
              מחק
            </button>
          </div>
        )}
      </div>
    );
  };

  const content = commentaries.map(renderSection);

  return (
    <>
      {isBookMode ? (
        <div ref={bookContainerRef} className="h-[75vh] overflow-x-auto overflow-y-hidden custom-scrollbar"
          style={{ columnWidth: '400px', columnGap: '3rem', columnFill: 'auto' }}>
          {content}
        </div>
      ) : (
        <div className="space-y-6">
          {content}
        </div>
      )}
      {message && (
        <div className={`text-sm font-bold mt-2 ${message.includes('נשמר') || message.includes('נמחק') ? 'text-green-600' : 'text-red-600'}`}>
          {message}
        </div>
      )}
      {canEdit && !editingId && (
        <button
          onClick={handleAdd}
          disabled={isSaving}
          className="flex items-center gap-2 mt-4 px-4 py-2 rounded-xl text-sm font-bold bg-[#F0EBE1] text-[#4A3B32] hover:bg-[#E5E0D8] transition-colors disabled:opacity-50"
        >
          {isSaving ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
          הוסף קטע ביאור
        </button>
      )}
    </>
  );
}
