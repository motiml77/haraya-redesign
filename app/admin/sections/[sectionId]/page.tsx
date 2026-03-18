'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Save, Eye, Plus, Trash2, ChevronRight, ChevronLeft, ChevronUp, ChevronDown } from 'lucide-react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { authFetch } from '@/lib/auth-fetch';
import { useAdminUser } from '../../admin-context';
import { MarkdownToolbar } from '@/components/MarkdownToolbar';
import { MarkdownRenderer, SimpleMarkdown } from '@/components/MarkdownRenderer';
import { convertWordHtmlToMarkdown } from '@/lib/word-to-markdown';
import { normalizeSectionContent } from '@/lib/normalize-section';
import { Breadcrumb } from '@/components/Breadcrumb';
import { TagInput } from '@/components/TagInput';
import { ContentBlock } from '@/lib/types';

// Decode URL-encoded tooltips for readable editing
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
    title: '', introduction: '', isEdited: false,
    bookTitle: '', bookId: '', parentId: '',
  });
  const [contentBlocks, setContentBlocks] = useState<ContentBlock[]>([]);
  const [tags, setTags] = useState<string[]>([]);
  const [existingComments, setExistingComments] = useState<any[]>([]);
  const [questionsForRabbi, setQuestionsForRabbi] = useState<any[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [breadcrumbItems, setBreadcrumbItems] = useState<{ label: string; href?: string }[]>([]);
  const [autoSaveStatus, setAutoSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle');
  const [siblings, setSiblings] = useState<{ id: string; title: string }[]>([]);

  const lastSavedRef = useRef<string>('');
  const dataRef = useRef({
    formData: { title: '', introduction: '', isEdited: false, bookTitle: '', bookId: '', parentId: '' },
    contentBlocks: [] as ContentBlock[], tags: [] as string[],
    existingComments: [] as any[], questionsForRabbi: [] as any[],
  });

  // Keep dataRef in sync for auto-save interval to read
  useEffect(() => {
    dataRef.current = { formData, contentBlocks, tags, existingComments, questionsForRabbi };
  });

  // Auto-save every 20 seconds
  useEffect(() => {
    if (isLoading) return;
    const interval = setInterval(async () => {
      const { formData: fd, contentBlocks: cb, tags: t, existingComments: ec, questionsForRabbi: q } = dataRef.current;
      const payload = {
        title: fd.title, introduction: fd.introduction, isEdited: fd.isEdited,
        tags: t, contentBlocks: cb, comments: ec, questionsForRabbi: q,
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
          // Normalize legacy data to contentBlocks
          const normalized = normalizeSectionContent(data);

          setFormData({
            title: data.title || '',
            introduction: data.introduction || '',
            isEdited: data.isEdited || false,
            bookTitle: data.bookTitle || '',
            bookId: data.bookId || '',
            parentId: data.parentId || '',
          });

          // Decode tooltips in content blocks
          const decodedBlocks: ContentBlock[] = (normalized.contentBlocks || []).map((b: ContentBlock) => ({
            ...b,
            sourceText: decodeTooltips(b.sourceText || ''),
            commentaryText: decodeTooltips(b.commentaryText || ''),
          }));
          setContentBlocks(decodedBlocks);

          // Fetch siblings for prev/next navigation
          if (data.bookId) {
            fetch(`/api/sections?bookId=${data.bookId}`)
              .then(r => r.json())
              .then((sections: any[]) => {
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
          const loadedComments = data.comments || [];
          const loadedQuestions = data.questionsForRabbi || [];
          setExistingComments(loadedComments);
          setQuestionsForRabbi(loadedQuestions);

          // Set initial save snapshot
          lastSavedRef.current = JSON.stringify({
            title: data.title || '', introduction: data.introduction || '', isEdited: data.isEdited || false,
            tags: Array.isArray(data.tags) ? data.tags : (data.tags ? data.tags.split(',').map((t: string) => t.trim()).filter(Boolean) : []),
            contentBlocks: decodedBlocks, comments: loadedComments, questionsForRabbi: loadedQuestions,
          });

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

  // Block operations
  const updateBlockField = (blockId: string, field: 'sourceText' | 'commentaryText', value: string) => {
    setContentBlocks(prev => prev.map(b => b.id === blockId ? { ...b, [field]: value } : b));
  };

  const addBlock = () => {
    setContentBlocks(prev => [...prev, { id: `cb_${Date.now()}`, sourceText: '', commentaryText: '' }]);
  };

  const deleteBlock = (blockId: string) => {
    if (contentBlocks.length <= 1) return;
    setContentBlocks(prev => prev.filter(b => b.id !== blockId));
  };

  const moveBlock = (index: number, direction: 'up' | 'down') => {
    setContentBlocks(prev => {
      const arr = [...prev];
      const target = direction === 'up' ? index - 1 : index + 1;
      if (target < 0 || target >= arr.length) return prev;
      [arr[index], arr[target]] = [arr[target], arr[index]];
      return arr;
    });
  };

  const handleSave = async () => {
    setIsSaving(true);
    setSaveMessage('');
    try {
      const payload = {
        title: formData.title,
        introduction: formData.introduction,
        isEdited: formData.isEdited,
        tags,
        contentBlocks,
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
    const question = prompt('מה השאלה לרב על החלק הנוכחי?', '');
    if (question) {
      setQuestionsForRabbi([...questionsForRabbi, {
        id: Date.now(), author: user?.name || 'עורך',
        date: new Date().toISOString().split('T')[0],
        text: question, paragraphTitle: formData.title || 'ללא כותרת',
        replies: [], resolved: false,
      }]);
    }
  };

  // Word paste handler for block textareas
  const handleWordPaste = (e: React.ClipboardEvent<HTMLTextAreaElement>, blockId: string, field: 'sourceText' | 'commentaryText') => {
    const html = e.clipboardData?.getData('text/html');
    if (!html || !/class="?Mso|mso-|<o:p>/i.test(html)) return;
    e.preventDefault();
    const markdown = convertWordHtmlToMarkdown(html);
    const target = e.currentTarget;
    const start = target.selectionStart;
    const end = target.selectionEnd;
    const block = contentBlocks.find(b => b.id === blockId);
    if (!block) return;
    const current = block[field];
    const newText = current.substring(0, start) + markdown + current.substring(end);
    updateBlockField(blockId, field, newText);
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
          {/* Section details */}
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

          {/* Introduction */}
          <div className="bg-white p-6 rounded-2xl shadow-sm border border-[#E5E0D8] space-y-4">
            <h2 className="text-xl font-bold text-[#8C2B2B] border-b border-[#F0EBE1] pb-3">הקדמה</h2>
            <textarea name="introduction" value={formData.introduction} onChange={handleInputChange}
              className="w-full p-4 h-28 rounded-xl border border-[#E5E0D8] bg-[#FAF8F5] focus:ring-2 focus:ring-[#8C2B2B] outline-none resize-y font-serif text-base leading-loose" placeholder="הקדמה לפרק (אופציונלי)..." />
          </div>

          {/* Content Blocks */}
          {contentBlocks.map((block, index) => {
            const sourceRef = React.createRef<HTMLTextAreaElement>();
            const commentaryRef = React.createRef<HTMLTextAreaElement>();
            return (
              <div key={block.id} className="bg-white rounded-2xl shadow-sm border border-[#E5E0D8] overflow-hidden">
                {/* Block header */}
                <div className="p-4 border-b border-[#E5E0D8] bg-[#FAF8F5] flex justify-between items-center">
                  <h3 className="font-bold text-[#4A3B32]">קטע {index + 1}</h3>
                  <div className="flex gap-1">
                    <button onClick={() => moveBlock(index, 'up')} disabled={index === 0}
                      className="p-1.5 rounded-md text-[#8C7A6B] hover:bg-[#E5E0D8] disabled:opacity-30 transition-colors"><ChevronUp size={16} /></button>
                    <button onClick={() => moveBlock(index, 'down')} disabled={index === contentBlocks.length - 1}
                      className="p-1.5 rounded-md text-[#8C7A6B] hover:bg-[#E5E0D8] disabled:opacity-30 transition-colors"><ChevronDown size={16} /></button>
                    {contentBlocks.length > 1 && (
                      <button onClick={() => deleteBlock(block.id)}
                        className="p-1.5 rounded-md text-red-500 hover:bg-red-50 transition-colors"><Trash2 size={16} /></button>
                    )}
                  </div>
                </div>

                {/* Source text */}
                <div className="border-b border-[#E5E0D8]">
                  <div className="px-4 pt-3 text-sm font-bold text-[#8C7A6B]">טקסט מקור</div>
                  <MarkdownToolbar textareaRef={sourceRef} onAskRabbi={handleAskRabbi} />
                  <textarea ref={sourceRef} value={block.sourceText}
                    onChange={(e) => updateBlockField(block.id, 'sourceText', e.target.value)}
                    onPaste={(e) => handleWordPaste(e, block.id, 'sourceText')}
                    className="w-full p-4 h-36 focus:outline-none resize-y font-serif text-lg leading-loose" placeholder="טקסט המקור..." />
                </div>

                {/* Commentary text */}
                <div>
                  <div className="px-4 pt-3 text-sm font-bold text-[#8C7A6B]">ביאור</div>
                  <MarkdownToolbar textareaRef={commentaryRef} />
                  <textarea ref={commentaryRef} value={block.commentaryText}
                    onChange={(e) => updateBlockField(block.id, 'commentaryText', e.target.value)}
                    onPaste={(e) => handleWordPaste(e, block.id, 'commentaryText')}
                    className="w-full p-4 h-36 focus:outline-none resize-y" placeholder="ביאור והרחבה..." />
                </div>
              </div>
            );
          })}

          {/* Add block button */}
          <button onClick={addBlock}
            className="flex items-center gap-2 justify-center w-full py-3 rounded-xl border-2 border-dashed border-[#E5E0D8] text-[#8C7A6B] hover:text-[#8C2B2B] hover:border-[#8C2B2B] transition-all text-sm font-bold">
            <Plus size={18} /> הוסף קטע תוכן חדש
          </button>

          {/* Tags */}
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
            <div className="space-y-6">
              {contentBlocks.map((block, index) => (
                <div key={block.id}>
                  {(block.sourceText || block.commentaryText) ? (
                    <div className="space-y-3">
                      {block.sourceText && (
                        <div className="font-serif text-lg leading-loose text-[#2C2A29] text-justify p-4 bg-[#FAF8F5] rounded-xl border border-[#E5E0D8]">
                          {index === 0 && <h3 className="text-base font-bold text-[#8C2B2B] font-serif mb-3">מקור</h3>}
                          <MarkdownRenderer>{block.sourceText}</MarkdownRenderer>
                        </div>
                      )}
                      {block.commentaryText && (
                        <div className="text-base leading-relaxed text-[#4A3B32] p-4">
                          {index === 0 && <h3 className="text-base font-bold text-[#8C2B2B] font-serif mb-3 border-b border-[#F0EBE1] pb-2">ביאורים והרחבות</h3>}
                          <SimpleMarkdown>{block.commentaryText}</SimpleMarkdown>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="text-center py-4 text-sm text-[#8C7A6B]">קטע {index + 1} — ריק</div>
                  )}
                  {index < contentBlocks.length - 1 && <hr className="border-[#E5E0D8] my-2" />}
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
