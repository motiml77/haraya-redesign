'use client';

import React, { useState, useRef, useEffect, ReactNode } from 'react';
import { Pencil, Check, X, Loader2 } from 'lucide-react';
import { MarkdownToolbar } from '@/components/MarkdownToolbar';
import { useWordPasteHandler } from '@/hooks/use-word-paste';

interface InlineEditorProps {
  value: string;
  onSave: (newValue: string) => Promise<void>;
  renderContent: ReactNode;
  canEdit: boolean;
  minHeight?: string;
}

export function InlineEditor({ value, onSave, renderContent, canEdit, minHeight = '120px' }: InlineEditorProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(value);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useWordPasteHandler(textareaRef, setEditValue, () => editValue);

  useEffect(() => {
    if (isEditing && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [isEditing]);

  // Sync external value changes
  useEffect(() => {
    if (!isEditing) setEditValue(value);
  }, [value, isEditing]);

  const handleSave = async () => {
    if (isSaving) return;
    setIsSaving(true);
    setMessage('');
    try {
      await onSave(editValue);
      setIsEditing(false);
      setMessage('נשמר!');
      setTimeout(() => setMessage(''), 2000);
    } catch {
      setMessage('שגיאה בשמירה');
      setTimeout(() => setMessage(''), 3000);
    }
    setIsSaving(false);
  };

  const handleCancel = () => {
    setEditValue(value);
    setIsEditing(false);
    setMessage('');
  };

  // Handle textarea auto-resize
  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setEditValue(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = e.target.scrollHeight + 'px';
  };

  if (!canEdit) return <>{renderContent}</>;

  return (
    <div>
      {isEditing ? (
        <div className="space-y-0">
          <MarkdownToolbar textareaRef={textareaRef} />
          <textarea
            ref={textareaRef}
            value={editValue}
            onChange={handleInput}
            className="w-full p-4 rounded-b-xl border border-[#E5E0D8] border-t-0 bg-[#FAF8F5] focus:ring-2 focus:ring-[#8C2B2B] outline-none resize-none font-serif leading-relaxed"
            style={{ minHeight }}
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
            {message && (
              <span className={`text-sm font-bold ${message.includes('נשמר') ? 'text-green-600' : 'text-red-600'}`}>
                {message}
              </span>
            )}
          </div>
        </div>
      ) : (
        <div>
          {renderContent}
          <div className="flex items-center gap-2 mt-3">
            <button
              onClick={() => setIsEditing(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#E5E0D8] text-[#8C7A6B] hover:text-[#8C2B2B] hover:border-[#8C2B2B] transition-all text-xs font-bold"
              title="ערוך"
            >
              <Pencil size={14} />
              ערוך טקסט
            </button>
            {message && (
              <span className={`text-sm font-bold ${message.includes('נשמר') ? 'text-green-600' : 'text-red-600'}`}>
                {message}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
