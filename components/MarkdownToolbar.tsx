'use client';

import React from 'react';
import { Bold, Italic, Underline, Link as LinkIcon, MessageSquare, List, Heading, Quote, Superscript } from 'lucide-react';

export function MarkdownToolbar({ textareaRef, onAskRabbi }: { textareaRef: React.RefObject<HTMLTextAreaElement | null>, onAskRabbi?: () => void }) {
  // Use native setter to bypass React's internal value tracker,
  // so the dispatched 'input' event properly triggers onChange
  const setNativeValue = (textarea: HTMLTextAreaElement, value: string) => {
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')?.set;
    if (setter) {
      setter.call(textarea, value);
    } else {
      textarea.value = value;
    }
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
  };

  const insertText = (prefix: string, suffix: string = '') => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const text = textarea.value;
    const selectedText = text.substring(start, end);
    const newText = text.substring(0, start) + prefix + selectedText + suffix + text.substring(end);
    setNativeValue(textarea, newText);
    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(start + prefix.length, end + prefix.length);
    }, 0);
  };

  const insertLink = () => {
    const url = prompt('הכנס כתובת קישור (URL):', 'https://');
    if (url) insertText('[', `](${url})`);
  };

  const insertTooltip = () => {
    const explanation = prompt('הכנס את הביאור למילה (יופיע בבועה):', '');
    if (explanation) insertText('[', `](tooltip:${explanation})`);
  };

  const insertFootnote = () => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    const text = textarea.value;
    // Count existing footnotes to determine next number
    const matches = text.match(/\[\^\d+\]/g) || [];
    const existingNums = matches.map(m => parseInt(m.replace(/\[\^|\]/g, '')));
    const nextNum = existingNums.length > 0 ? Math.max(...existingNums) + 1 : 1;
    // Insert [^N] at cursor position and [^N]: at the end
    const start = textarea.selectionStart;
    const marker = `[^${nextNum}]`;
    const definition = `\n[^${nextNum}]: `;
    const newText = text.substring(0, start) + marker + text.substring(start) + definition;
    setNativeValue(textarea, newText);
    // Move cursor to end of definition for typing
    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(newText.length, newText.length);
    }, 0);
  };

  const insertLinePrefix = (prefix: string) => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const text = textarea.value;
    let lineStart = start;
    while (lineStart > 0 && text[lineStart - 1] !== '\n') lineStart--;
    const newText = text.substring(0, lineStart) + prefix + text.substring(lineStart);
    setNativeValue(textarea, newText);
    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(start + prefix.length, end + prefix.length);
    }, 0);
  };

  return (
    <div className="flex flex-wrap gap-1 bg-[#F0EBE1] p-2 rounded-t-xl border-b border-[#E5E0D8]">
      <button type="button" onClick={() => insertText('**', '**')} className="p-1.5 hover:bg-white rounded text-[#4A3B32] transition-colors" title="מודגש"><Bold size={18} /></button>
      <button type="button" onClick={() => insertText('*', '*')} className="p-1.5 hover:bg-white rounded text-[#4A3B32] transition-colors" title="נטוי"><Italic size={18} /></button>
      <button type="button" onClick={() => insertText('<u>', '</u>')} className="p-1.5 hover:bg-white rounded text-[#4A3B32] transition-colors" title="קו תחתון"><Underline size={18} /></button>
      <div className="w-px h-6 bg-[#D5D0C8] mx-1 self-center"></div>
      <button type="button" onClick={() => insertLinePrefix('### ')} className="p-1.5 hover:bg-white rounded text-[#4A3B32] transition-colors" title="כותרת"><Heading size={18} /></button>
      <button type="button" onClick={() => insertLinePrefix('- ')} className="p-1.5 hover:bg-white rounded text-[#4A3B32] transition-colors" title="רשימה"><List size={18} /></button>
      <button type="button" onClick={() => insertLinePrefix('1. ')} className="p-1.5 hover:bg-white rounded text-[#4A3B32] transition-colors" title="רשימה ממוספרת"><List size={18} /></button>
      <button type="button" onClick={() => insertLinePrefix('> ')} className="p-1.5 hover:bg-white rounded text-[#4A3B32] transition-colors" title="ציטוט"><Quote size={18} /></button>
      <div className="w-px h-6 bg-[#D5D0C8] mx-1 self-center"></div>
      <button type="button" onClick={insertLink} className="p-1.5 hover:bg-white rounded text-[#4A3B32] transition-colors" title="הוסף קישור"><LinkIcon size={18} /></button>
      <button type="button" onClick={insertTooltip} className="p-1.5 hover:bg-white rounded text-[#4A3B32] transition-colors" title="הוסף ביאור מילה (בועה)"><MessageSquare size={18} /></button>
      <button type="button" onClick={insertFootnote} className="p-1.5 hover:bg-white rounded text-[#4A3B32] transition-colors" title="הוסף הערת שוליים"><Superscript size={18} /></button>
      {onAskRabbi && (
        <>
          <div className="w-px h-6 bg-[#D5D0C8] mx-1 self-center"></div>
          <button type="button" onClick={onAskRabbi} className="p-1.5 hover:bg-white rounded text-[#8C2B2B] transition-colors font-bold text-sm flex items-center gap-1" title="שאל את הרב על הפסקה">
            <MessageSquare size={16} />
            שאלת רב
          </button>
        </>
      )}
    </div>
  );
}
