'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Save, Eye, Plus, Trash2, Check, ChevronRight, ChevronLeft } from 'lucide-react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { authFetch } from '@/lib/auth-fetch';
import { useAdminUser } from '../../admin-context';
import { MarkdownToolbar } from '@/components/MarkdownToolbar';
import { MarkdownRenderer, SimpleMarkdown } from '@/components/MarkdownRenderer';
import { useWordPasteHandler } from '@/hooks/use-word-paste';
import { convertWordHtmlToMarkdown } from '@/lib/word-to-markdown';
import { Breadcrumb } from '@/components/Breadcrumb';
import { TagInput } from '@/components/TagInput';

// Decode URL-encoded tooltips for readable editing
// For encoded content: find last ) before next [ or newline (avoids paren-depth issues)
function decodeTooltips(text: string): string {
  if (!text) return text;
  let output = '';
  let i = 0;
  while (i < text.length) {
    const bracketStart = text.indexOf('[', i);
    if (bracketStart === -1) { output += text.slice(i); break; }
    output += text.slice(i, bracketStart);
    const bracketEnd = text.indexOf(']', bracketStart + 1);
    if (bracketEnd === -1) { output += text.slice(bracketStart); break; }
    const word = text.slice(bracketStart + 1, bracketEnd);
    const afterBracket = text.substring(bracketEnd + 1, bracketEnd + 20);
    const tooltipPrefix = afterBracket.match(/^\s*\(tooltip:/);
    if (tooltipPrefix) {
      const tooltipStart = bracketEnd + 1 + tooltipPrefix[0].length;
      const isUrlEncoded = /^%[0-9A-Fa-f]{2}/.test(text.substring(tooltipStart, tooltipStart + 3));
      let j: number;
      if (isUrlEncoded) {
        // Find last ) before next [ or newline
        let searchEnd = text.length;
        const nextNl = text.indexOf('\n', tooltipStart);
        if (nextNl !== -1 && nextNl < searchEnd) searchEnd = nextNl;
        const nextBr = text.indexOf('[', tooltipStart);
        if (nextBr !== -1 && nextBr < searchEnd) searchEnd = nextBr;
        j = -1;
        for (let k = searchEnd - 1; k >= tooltipStart; k--) {
          if (text[k] === ')') { j = k; break; }
        }
        if (j === -1) { output += '['; i = bracketStart + 1; continue; }
      } else {
        let depth = 1;
        j = tooltipStart;
        while (j < text.length && depth > 0) {
          if (text[j] === '(') depth++;
          else if (text[j] === ')') depth--;
          if (depth > 0) j++;
        }
        if (depth !== 0) { output += '['; i = bracketStart + 1; continue; }
      }
      const raw = text.slice(tooltipStart, j);
      let decoded: string;
      try { decoded = decodeURIComponent(raw); } catch { decoded = raw; }
      output += `[${word}](tooltip:${decoded})`;
      i = j + 1;
      continue;
    }
    output += '[';
    i = bracketStart + 1;
  }
  return output;
}

export default function SectionEditorPage() {
  const { sectionId } = useParams<{ sectionId: string }>();
  const { user } = useAdminUser();

  const [formData, setFormData] = useState({
    title: '', originalText: '', introduction: '', isEdited: false,
    bookTitle: '', bookId: '', parentId: '',
  });
  const [tags, setTags] = useState<string[]>([]);
  const [commentaries, setCommentaries] = useState<any[]>([]);
  const [existingComments, setExistingComments] = useState<any[]>([]);
  const [questionsForRabbi, setQuestionsForRabbi] = useState<any[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [breadcrumbItems, setBreadcrumbItems] = useState<{ label: string; href?: string }[]>([]);
  const [autoSaveStatus, setAutoSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle');
  const [siblings, setSiblings] = useState<{ id: string; title: string }[]>([]);

  const originalTextRef = useRef<HTMLTextAreaElement>(null);
  const lastSavedRef = useRef<string>('');
  const dataRef = useRef({ formData: { title: '', originalText: '', introduction: '', isEdited: false, bookTitle: '', bookId: '', parentId: '' }, tags: [] as string[], commentaries: [] as any[], existingComments: [] as any[], questionsForRabbi: [] as any[] });

  useWordPasteHandler(
    originalTextRef,
    (val) => setFormData(prev => ({ ...prev, originalText: val })),
    () => formData.originalText
  );

  // Keep dataRef in sync for auto-save interval to read
  useEffect(() => {
    dataRef.current = { formData, tags, commentaries, existingComments, questionsForRabbi };
  });

  // Auto-save every 20 seconds
  useEffect(() => {
    if (isLoading) return;
    const interval = setInterval(async () => {
      const { formData: fd, tags: t, commentaries: c, existingComments: ec, questionsForRabbi: q } = dataRef.current;
      const payload = {
        title: fd.title, originalText: fd.originalText, introduction: fd.introduction, isEdited: fd.isEdited,
        tags: t, commentary: c, comments: ec, questionsForRabbi: q,
      };
      const payloadStr = JSON.stringify(payload);
      if (payloadStr === lastSavedRef.current) return;

      setAutoSaveStatus('saving');
      try {
        const res = await authFetch(`/api/sections/${sectionId}`, {
          method: 'PUT', body: payloadStr,
        });
        if (res.ok) {
          lastSavedRef.current = payloadStr;
          setAutoSaveStatus('saved');
          setTimeout(() => setAutoSaveStatus(prev => prev === 'saved' ? 'idle' : prev), 4000);
        }
      } catch {}
    }, 20000);
    return () => clearInterval(interval);
  }, [sectionId, isLoading]);

  useEffect(() => {
    fetch(`/api/sections/${sectionId}`)
      .then(res => res.json())
      .then(async (data) => {
        if (data && !data.error) {
          setFormData({
            title: data.title || '',
            originalText: decodeTooltips(data.originalText || ''),
            introduction: data.introduction || '',
            isEdited: data.isEdited || false,
            bookTitle: data.bookTitle || '',
            bookId: data.bookId || '',
            parentId: data.parentId || '',
          });

          // Fetch siblings for prev/next navigation
          if (data.bookId) {
            fetch(`/api/sections?bookId=${data.bookId}`)
              .then(r => r.json())
              .then((sections: any[]) => {
                // Flatten tree depth-first for reading order
                const roots = sections.filter(s => !s.parentId).sort((a, b) => (a.orderIndex || 0) - (b.orderIndex || 0));
                const flat: { id: string; title: string }[] = [];
                const addWithChildren = (node: any) => {
                  flat.push({ id: node.id, title: node.title });
                  sections.filter(s => s.parentId === node.id).sort((a, b) => (a.orderIndex || 0) - (b.orderIndex || 0)).forEach(addWithChildren);
                };
                roots.forEach(addWithChildren);
                setSiblings(flat);
              })
              .catch(() => {});
          }
          setTags(Array.isArray(data.tags) ? data.tags : (data.tags ? data.tags.split(',').map((t: string) => t.trim()).filter(Boolean) : []));
          const decodedCommentary = (data.commentary || []).map((c: any) => ({ ...c, text: decodeTooltips(c.text || '') }));
          const loadedComments = data.comments || [];
          const loadedQuestions = data.questionsForRabbi || [];
          setCommentaries(decodedCommentary);
          setExistingComments(loadedComments);
          setQuestionsForRabbi(loadedQuestions);

          // Set initial save snapshot so auto-save knows the baseline
          lastSavedRef.current = JSON.stringify({
            title: data.title || '', originalText: decodeTooltips(data.originalText || ''), introduction: data.introduction || '', isEdited: data.isEdited || false,
            tags: Array.isArray(data.tags) ? data.tags : (data.tags ? data.tags.split(',').map((t: string) => t.trim()).filter(Boolean) : []),
            commentary: decodedCommentary, comments: loadedComments, questionsForRabbi: loadedQuestions,
          });

          // Build breadcrumbs by walking up parentId chain
          await buildBreadcrumbs(data);
        }
        setIsLoading(false);
      })
      .catch(() => setIsLoading(false));
  }, [sectionId]);

  const buildBreadcrumbs = async (section: any) => {
    const items: { label: string; href?: string }[] = [
      { label: 'ספרים', href: '/admin/books' },
    ];

    if (section.bookId) {
      items.push({ label: section.bookTitle || 'ספר', href: `/admin/books` });
    }

    // Walk up parentId chain to build path
    if (section.parentId) {
      const ancestors: { title: string; id: string }[] = [];
      let currentParentId = section.parentId;
      while (currentParentId) {
        try {
          const res = await fetch(`/api/sections/${currentParentId}`);
          const parent = await res.json();
          if (parent && !parent.error) {
            ancestors.unshift({ title: parent.title, id: parent.id });
            currentParentId = parent.parentId;
          } else break;
        } catch { break; }
      }
      ancestors.forEach(a => {
        items.push({ label: a.title, href: `/admin/sections/${a.id}` });
      });
    }

    items.push({ label: section.title || 'חלק' });
    setBreadcrumbItems(items);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value, type } = e.target;
    if (type === 'checkbox') {
      setFormData({ ...formData, [name]: (e.target as HTMLInputElement).checked });
    } else {
      setFormData({ ...formData, [name]: value });
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    setSaveMessage('');
    try {
      const payload = {
        title: formData.title,
        originalText: formData.originalText,
        introduction: formData.introduction,
        isEdited: formData.isEdited,
        tags,
        commentary: commentaries,
        comments: existingComments,
        questionsForRabbi,
      };
      const payloadStr = JSON.stringify(payload);
      const res = await authFetch(`/api/sections/${sectionId}`, {
        method: 'PUT', body: payloadStr,
      });
      if (res.ok) {
        lastSavedRef.current = payloadStr;
        setSaveMessage('נשמר בהצלחה!');
        setTimeout(() => setSaveMessage(''), 3000);
      } else {
        const data = await res.json();
        setSaveMessage(data.error || 'שגיאה בשמירה');
      }
    } catch { setSaveMessage('שגיאה בשמירה'); }
    setIsSaving(false);
  };

  const handleAskRabbi = () => {
    // Capture selected text from textarea
    const textarea = originalTextRef.current;
    let selectedText = '';
    if (textarea) {
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      if (start !== end) selectedText = textarea.value.substring(start, end);
    }

    const question = prompt('מה השאלה לרב על החלק הנוכחי?', '');
    if (question) {
      setQuestionsForRabbi([...questionsForRabbi, {
        id: Date.now(), author: user?.name || 'עורך',
        date: new Date().toISOString().split('T')[0],
        text: question, paragraphTitle: formData.title || 'ללא כותרת',
        selectedText: selectedText || undefined,
        replies: [],
        resolved: false,
      }]);
    }
  };

  if (isLoading) return <p className="text-center text-[#8C7A6B] py-12">טוען...</p>;

  return (
    <div>
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <Breadcrumb items={breadcrumbItems} />
        </div>
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5 text-xs text-[#B8B0A6]">
            <span className={`w-2 h-2 rounded-full transition-colors ${autoSaveStatus === 'saving' ? 'bg-yellow-400 animate-pulse' : 'bg-green-500'}`} />
            {autoSaveStatus === 'saving' ? 'שומר...' : autoSaveStatus === 'saved' ? 'נשמר אוטומטית' : 'שמירה אוטומטית'}
          </span>
          {saveMessage && (
            <span className={`text-sm font-bold ${saveMessage.includes('שגיאה') ? 'text-red-600' : 'text-green-600'}`}>{saveMessage}</span>
          )}
          <button onClick={handleSave} disabled={isSaving}
            className={`flex items-center gap-2 px-6 py-2.5 rounded-full transition-colors font-medium shadow-sm ${isSaving ? 'bg-[#D5D0C8] text-[#8C7A6B] cursor-not-allowed' : 'bg-[#8C2B2B] text-white hover:bg-[#7A2525]'}`}>
            <Save size={20} />
            {isSaving ? 'שומר...' : 'שמור ופרסם'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Editor */}
        <div className="space-y-6">
          <div className="bg-white p-6 rounded-2xl shadow-sm border border-[#E5E0D8] space-y-4">
            <div className="flex justify-between items-center border-b border-[#F0EBE1] pb-3">
              <h2 className="text-xl font-bold text-[#4A3B32]">פרטי החלק</h2>
              <label className="flex items-center gap-2 cursor-pointer bg-[#FAF8F5] px-3 py-1.5 rounded-full border border-[#E5E0D8]">
                <div className="relative">
                  <input type="checkbox" name="isEdited" checked={formData.isEdited} onChange={handleInputChange} className="sr-only" />
                  <div className={`block w-10 h-6 rounded-full transition-colors ${formData.isEdited ? 'bg-green-500' : 'bg-red-400'}`}></div>
                  <div className={`dot absolute left-1 top-1 bg-white w-4 h-4 rounded-full transition-transform ${formData.isEdited ? 'transform translate-x-4' : ''}`}></div>
                </div>
                <span className="text-sm font-bold text-[#4A3B32]">{formData.isEdited ? 'ערוך' : 'לא ערוך'}</span>
              </label>
            </div>
            <div>
              <label className="block text-sm font-bold text-[#8C7A6B] mb-1">כותרת</label>
              <input type="text" name="title" value={formData.title} onChange={handleInputChange}
                className="w-full p-3 rounded-xl border border-[#E5E0D8] bg-[#FAF8F5] focus:ring-2 focus:ring-[#8C2B2B] outline-none" />
            </div>
          </div>

          <div className="bg-white p-6 rounded-2xl shadow-sm border border-[#E5E0D8] space-y-4">
            <h2 className="text-xl font-bold text-[#8C2B2B] border-b border-[#F0EBE1] pb-3">הקדמה</h2>
            <textarea name="introduction" value={formData.introduction} onChange={handleInputChange}
              className="w-full p-4 h-28 rounded-xl border border-[#E5E0D8] bg-[#FAF8F5] focus:ring-2 focus:ring-[#8C2B2B] outline-none resize-y font-serif text-base leading-loose" placeholder="הקדמה לפרק (אופציונלי)..." />
          </div>

          <div className="bg-white rounded-2xl shadow-sm border border-[#E5E0D8] overflow-hidden">
            <div className="p-4 border-b border-[#E5E0D8] bg-[#FAF8F5]">
              <h2 className="text-xl font-bold text-[#4A3B32]">טקסט המקור</h2>
              <p className="text-xs text-[#8C7A6B] mt-1">סמן מילה ולחץ על סמל הבועה כדי להוסיף ביאור צף.</p>
            </div>
            <MarkdownToolbar textareaRef={originalTextRef} onAskRabbi={handleAskRabbi} />
            <textarea ref={originalTextRef} name="originalText" value={formData.originalText} onChange={handleInputChange}
              className="w-full p-4 h-48 focus:outline-none resize-y font-serif text-lg leading-loose" placeholder="הזן את טקסט המקור כאן..." />
          </div>

          <div className="bg-white p-6 rounded-2xl shadow-sm border border-[#E5E0D8] space-y-4">
            <div className="flex justify-between items-center border-b border-[#F0EBE1] pb-3">
              <h2 className="text-xl font-bold text-[#8C2B2B]">ביאור והרחבה</h2>
              <button onClick={() => setCommentaries([...commentaries, { id: Date.now(), text: '' }])}
                className="flex items-center gap-1 text-sm text-[#8C2B2B] hover:text-[#7A2525] font-bold bg-[#F0EBE1] px-3 py-1.5 rounded-lg transition-colors">
                <Plus size={16} /> הוסף קטע
              </button>
            </div>
            {commentaries.map((commentary, index) => {
              const ref = React.createRef<HTMLTextAreaElement>();
              return (
                <div key={commentary.id} className="border border-[#E5E0D8] rounded-xl overflow-hidden relative">
                  <div className="absolute top-2 left-2 z-10">
                    <button onClick={() => setCommentaries(commentaries.filter(c => c.id !== commentary.id))}
                      className="p-1.5 bg-white rounded-md text-red-500 hover:bg-red-50 transition-colors shadow-sm border border-red-100"><Trash2 size={16} /></button>
                  </div>
                  <MarkdownToolbar textareaRef={ref} />
                  <textarea ref={ref} value={commentary.text}
                    onChange={(e) => setCommentaries(commentaries.map(c => c.id === commentary.id ? { ...c, text: e.target.value } : c))}
                    onPaste={(e) => {
                      const html = e.clipboardData?.getData('text/html');
                      if (!html || !/class="?Mso|mso-|<o:p>/i.test(html)) return;
                      e.preventDefault();
                      const markdown = convertWordHtmlToMarkdown(html);
                      const target = e.currentTarget;
                      const start = target.selectionStart;
                      const end = target.selectionEnd;
                      const current = commentary.text;
                      const newText = current.substring(0, start) + markdown + current.substring(end);
                      setCommentaries(commentaries.map(c => c.id === commentary.id ? { ...c, text: newText } : c));
                    }}
                    className="w-full p-4 h-32 focus:outline-none resize-y" placeholder={`קטע ביאור ${index + 1}...`} />
                </div>
              );
            })}
          </div>

          <div className="bg-white p-6 rounded-2xl shadow-sm border border-[#E5E0D8]">
            <label className="block text-sm font-bold text-[#8C7A6B] mb-2">נושאים</label>
            <TagInput tags={tags} onChange={setTags} />
          </div>
        </div>

        {/* Live Preview */}
        <div className="lg:sticky lg:top-20 h-fit space-y-4">
          <h2 className="text-xl font-bold text-[#4A3B32] flex items-center gap-2">
            <Eye size={20} className="text-[#8C7A6B]" /> תצוגה מקדימה חיה
          </h2>
          <div className="bg-white p-6 sm:p-8 rounded-2xl shadow-lg border border-[#E5E0D8] max-h-[calc(100vh-10rem)] overflow-y-auto custom-scrollbar">
            <div className="mb-6 pb-4 border-b border-[#F0EBE1]">
              <h1 className="text-xl font-serif font-bold text-[#4A3B32]">{formData.bookTitle}</h1>
            </div>
            <h2 className="text-lg font-bold text-[#8C2B2B] mb-4 font-serif">{formData.title}</h2>
            {formData.introduction.trim() && (
              <div className="mb-6 p-4 bg-white rounded-xl border border-[#E5E0D8]">
                <h3 className="text-base font-bold text-[#8C2B2B] font-serif border-b border-[#F0EBE1] pb-2 mb-3">הקדמה</h3>
                <div className="font-serif leading-loose text-[#2C2A29] text-justify text-sm">
                  <MarkdownRenderer>{formData.introduction}</MarkdownRenderer>
                </div>
              </div>
            )}
            <div className="font-serif text-xl leading-loose text-[#2C2A29] text-justify mb-8 p-4 bg-[#FAF8F5] rounded-xl border border-[#E5E0D8]">
              <MarkdownRenderer>{formData.originalText}</MarkdownRenderer>
            </div>
            <h3 className="text-lg font-bold text-[#8C2B2B] mb-4 border-b border-[#F0EBE1] pb-2">ביאור והרחבה</h3>
            <div className="space-y-4">
              {commentaries.map(s => (
                <div key={s.id} className="text-base leading-relaxed text-[#4A3B32]">
                  <SimpleMarkdown>{s.text || '*טקסט ריק*'}</SimpleMarkdown>
                </div>
              ))}
            </div>
            <div className="mt-8 pt-4 border-t border-[#F0EBE1] flex flex-wrap gap-2">
              {tags.map((tag, idx) => (
                <span key={idx} className="px-2 py-1 bg-[#F0EBE1] text-[#6B5A4E] text-xs rounded-full">#{tag}</span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Prev/Next Navigation */}
      {siblings.length > 1 && (() => {
        const currentIdx = siblings.findIndex(s => s.id === sectionId);
        const prev = currentIdx > 0 ? siblings[currentIdx - 1] : null;
        const next = currentIdx >= 0 && currentIdx < siblings.length - 1 ? siblings[currentIdx + 1] : null;
        return (prev || next) ? (
          <div className="flex justify-between items-center mt-8 pt-6 border-t border-[#E5E0D8]">
            {prev ? (
              <Link href={`/admin/sections/${prev.id}`} className="flex items-center gap-2 text-[#8C2B2B] font-bold hover:underline">
                <ChevronRight size={18} /> הקודם: {prev.title}
              </Link>
            ) : <div />}
            {next ? (
              <Link href={`/admin/sections/${next.id}`} className="flex items-center gap-2 text-[#8C2B2B] font-bold hover:underline">
                הבא: {next.title} <ChevronLeft size={18} />
              </Link>
            ) : <div />}
          </div>
        ) : null;
      })()}
    </div>
  );
}
