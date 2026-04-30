'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { Share2, MessageCircle, Columns, Menu, Bookmark, BookOpen, ChevronDown, ChevronUp, ChevronLeft, ChevronRight, Loader2, User, Pencil, Trash2, Check, X, Reply, FileText, Plus } from 'lucide-react';
import { MarkdownRenderer, SimpleMarkdown } from '@/components/MarkdownRenderer';
import { Breadcrumb } from '@/components/Breadcrumb';
import { InlineEditor } from '@/components/InlineEditor';
import { AudioPlayer } from '@/components/AudioPlayer';
import { useEditAuth } from '@/hooks/use-edit-auth';
import { authFetch } from '@/lib/auth-fetch';
import { ContentBlock, YouTubeVideo } from '@/lib/types';
import { YouTubePlaylist } from '@/components/YouTubePlaylist';

export function SectionViewer({
  initialSection,
  book,
  siblings,
  breadcrumbItems
}: {
  initialSection: any;
  book: any;
  siblings: any[];
  breadcrumbItems: { label: string; href?: string }[];
}) {
  const bookId = book.id;
  const sectionId = initialSection.id;
  
  const [section, setSection] = useState<any>(initialSection);
  const [isMobileCommentaryOpen, setIsMobileCommentaryOpen] = useState(true);
  const [layoutMode, setLayoutMode] = useState<'split' | 'stacked'>('split');
  
  // Comments state
  const [newCommentText, setNewCommentText] = useState('');
  const [newCommentAuthor, setNewCommentAuthor] = useState('');
  const [isSubmittingComment, setIsSubmittingComment] = useState(false);
  const [editingCommentId, setEditingCommentId] = useState<number | null>(null);
  const [editCommentText, setEditCommentText] = useState('');
  const [replyingToId, setReplyingToId] = useState<number | null>(null);
  const [replyText, setReplyText] = useState('');
  const [isSavingComment, setIsSavingComment] = useState(false);
  
  // Bookmarks
  interface BookmarkItem { sectionId: string; bookId: string; title: string; bookTitle: string; }
  const [bookmarks, setBookmarks] = useState<BookmarkItem[]>([]);
  const [showBookmarks, setShowBookmarks] = useState(false);

  // Resizable split
  const [splitPercent, setSplitPercent] = useState(42);
  useEffect(() => {
    const saved = localStorage.getItem('kook_split_percent');
    if (saved) { const n = parseFloat(saved); if (n >= 20 && n <= 80) setSplitPercent(n); }
  }, []);
  const isDragging = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleDragStart = useCallback((e: React.MouseEvent | React.TouchEvent) => {
    e.preventDefault();
    isDragging.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, []);

  useEffect(() => {
    const handleMove = (clientX: number) => {
      if (!isDragging.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      // RTL: right edge is start, so percent = distance from right / total width
      const fromRight = rect.right - clientX;
      const pct = Math.min(80, Math.max(20, (fromRight / rect.width) * 100));
      setSplitPercent(pct);
    };
    const onMouseMove = (e: MouseEvent) => handleMove(e.clientX);
    const onTouchMove = (e: TouchEvent) => { if (e.touches.length) handleMove(e.touches[0].clientX); };
    const onEnd = () => {
      if (isDragging.current) {
        isDragging.current = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        // Persist
        setSplitPercent(prev => { localStorage.setItem('kook_split_percent', String(prev)); return prev; });
      }
    };
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onEnd);
    window.addEventListener('touchmove', onTouchMove);
    window.addEventListener('touchend', onEnd);
    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onEnd);
      window.removeEventListener('touchmove', onTouchMove);
      window.removeEventListener('touchend', onEnd);
    };
  }, []);

  const { user: editUser, canEdit, loading: authLoading } = useEditAuth();

  useEffect(() => {
    const saved = localStorage.getItem('kook_bookmarks');
    if (saved) try {
      const parsed = JSON.parse(saved);
      // Migrate old format (string[]) to new format
      if (Array.isArray(parsed) && parsed.length > 0 && typeof parsed[0] === 'string') {
        localStorage.removeItem('kook_bookmarks');
      } else {
        setBookmarks(parsed);
      }
    } catch {}
  }, []);

  const submitComment = async () => {
    if (!newCommentText.trim() || !newCommentAuthor.trim()) { alert('נא למלא שם ותגובה'); return; }
    setIsSubmittingComment(true);
    try {
      const res = await fetch(`/api/sections/${sectionId}/comments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ author: newCommentAuthor, text: newCommentText }),
      });
      if (res.ok) {
        const data = await res.json();
        setSection({ ...section, comments: [...(section.comments || []), data.comment] });
        setNewCommentText('');
        setNewCommentAuthor('');
      } else { alert('שגיאה בשליחת התגובה'); }
    } catch { alert('שגיאה בשליחת התגובה'); }
    setIsSubmittingComment(false);
  };

  const isBookmarked = bookmarks.some(b => b.sectionId === sectionId);
  const toggleBookmark = () => {
    const updated = isBookmarked
      ? bookmarks.filter(b => b.sectionId !== sectionId)
      : [...bookmarks, { sectionId, bookId, title: section.title, bookTitle: book.title }];
    setBookmarks(updated);
    localStorage.setItem('kook_bookmarks', JSON.stringify(updated));
  };

  const saveSectionField = async (updates: Record<string, any>) => {
    const res = await authFetch(`/api/sections/${sectionId}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
    const data = await res.json();
    if (!data.success) throw new Error(data.error || 'שגיאה בשמירה');
    const updated = { ...section, ...updates };
    setSection(updated);
  };

  // Content blocks
  const blocks: ContentBlock[] = section.contentBlocks || [];

  const saveBlockField = async (blockId: string, field: 'sourceText' | 'commentaryText', value: string) => {
    const updatedBlocks = blocks.map(b => b.id === blockId ? { ...b, [field]: value } : b);
    await saveSectionField({ contentBlocks: updatedBlocks });
  };

  const handleAddBlock = async () => {
    const newBlock: ContentBlock = { id: `cb_${Date.now()}`, sourceText: '', commentaryText: '' };
    await saveSectionField({ contentBlocks: [...blocks, newBlock] });
  };

  const handleDeleteBlock = async (blockId: string) => {
    if (!confirm('למחוק קטע תוכן זה?')) return;
    await saveSectionField({ contentBlocks: blocks.filter(b => b.id !== blockId) });
  };

  const canManageComments = editUser && ['admin', 'rabbi'].includes(editUser.role);

  const deleteComment = async (commentId: number) => {
    if (!confirm('למחוק תגובה זו?')) return;
    setIsSavingComment(true);
    try {
      const res = await authFetch(`/api/sections/${sectionId}/comments`, {
        method: 'DELETE',
        body: JSON.stringify({ commentId }),
      });
      if ((await res.json()).success) {
        const updated = { ...section, comments: (section.comments || []).filter((c: any) => c.id !== commentId) };
        setSection(updated);
      }
    } catch { }
    setIsSavingComment(false);
  };

  const saveCommentEdit = async (commentId: number) => {
    if (!editCommentText.trim()) return;
    setIsSavingComment(true);
    try {
      const res = await authFetch(`/api/sections/${sectionId}/comments`, {
        method: 'PUT',
        body: JSON.stringify({ commentId, text: editCommentText }),
      });
      if ((await res.json()).success) {
        const updated = {
          ...section,
          comments: (section.comments || []).map((c: any) =>
            c.id === commentId ? { ...c, text: editCommentText, editedAt: new Date().toISOString().split('T')[0] } : c
          ),
        };
        setSection(updated);
        setEditingCommentId(null);
      }
    } catch { }
    setIsSavingComment(false);
  };

  const submitReply = async (commentId: number) => {
    if (!replyText.trim()) return;
    setIsSavingComment(true);
    try {
      const updatedComments = (section.comments || []).map((c: any) =>
        c.id === commentId
          ? { ...c, replies: [...(c.replies || []), { id: Date.now(), author: editUser?.name || 'הרב המשיב', date: new Date().toISOString().split('T')[0], text: replyText }] }
          : c
      );
      await authFetch(`/api/sections/${sectionId}`, { method: 'PUT', body: JSON.stringify({ comments: updatedComments }) });
      const updated = { ...section, comments: updatedComments };
      setSection(updated);
      setReplyingToId(null);
      setReplyText('');
    } catch { }
    setIsSavingComment(false);
  };

  const currentIdx = siblings.findIndex((s: any) => s.id === sectionId);
  const prevSection = currentIdx > 0 ? siblings[currentIdx - 1] : null;
  const nextSection = currentIdx >= 0 && currentIdx < siblings.length - 1 ? siblings[currentIdx + 1] : null;

  // If section has no content but has children — show children list
  const hasContent = section.originalText || (section.contentBlocks && section.contentBlocks.length > 0);
  if (!hasContent && book?.sections) {
    const children = book.sections
      .filter((s: any) => s.parentId === sectionId)
      .sort((a: any, b: any) => (a.orderIndex || 0) - (b.orderIndex || 0));

    return (
      <div className="min-h-screen bg-[#F1E6D2] font-sans" dir="rtl">
        <header className="bg-[#E8DCC4] border-b border-[#D6C8A8] py-6 px-6">
          <div className="max-w-4xl mx-auto flex items-start gap-4">
            <Link href="/" className="p-2 rounded-full hover:bg-[#E8DCC4] transition-colors mt-1 shrink-0" title="חזרה לדף הראשי">
              <BookOpen size={28} className="text-[#B14F1C]" />
            </Link>
            <div className="flex-1">
              <Breadcrumb items={breadcrumbItems} />
              <h1 className="text-3xl font-serif font-bold text-[#1F1A14] mt-4">{section.title}</h1>
            </div>
          </div>
        </header>

        <main className="max-w-4xl mx-auto px-6 py-8">
          {children.length > 0 ? (
            <div className="space-y-3">
              {children.map((child: any) => (
                <Link key={child.id} href={`/book/${bookId}/${child.id}`}
                  className="flex items-center gap-4 bg-[#E8DCC4] p-5 border border-[#D6C8A8] hover:border-[#B14F1C] hover: transition-all group">
                  <div className="flex items-center gap-3 flex-1">
                    <FileText size={20} className="text-[#6B5D4F] group-hover:text-[#B14F1C] transition-colors" />
                    <span className="font-bold text-[#1F1A14]">{child.title}</span>
                  </div>
                  {child.hasContent && (
                    <span className={`w-2.5 h-2.5 rounded-full ${child.isEdited ? 'bg-green-500' : 'bg-red-400'}`}
                      title={child.isEdited ? 'ערוך' : 'לא ערוך'}></span>
                  )}
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-center text-[#6B5D4F] py-12">אין תוכן בחלק זה.</p>
          )}
        </main>
      </div>
    );
  }

  const tagsArray = Array.isArray(section.tags) ? section.tags : (typeof section.tags === 'string' ? section.tags.split(',').map((t: string) => t.trim()).filter(Boolean) : []);

  return (
    <div className="min-h-screen flex flex-col font-sans bg-[#F1E6D2]">
      {/* Header */}
      <header className="bg-[#E8DCC4] border-b border-[#D6C8A8] py-4 px-6 sticky top-0 z-50" dir="rtl">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <div className="flex items-start gap-3">
            <Link href="/" className="p-2 rounded-full hover:bg-[#E8DCC4] transition-colors mt-0.5 shrink-0" title="חזרה לדף הראשי">
              <BookOpen size={28} className="text-[#B14F1C]" />
            </Link>
            <div>
              <Breadcrumb items={breadcrumbItems} />
              <h1 className="text-2xl font-serif font-bold text-[#1F1A14] mt-1">{section.title}</h1>
            </div>
          </div>
          <div className="flex gap-3 items-center">
            {!authLoading && editUser && (
              <Link href="/admin" className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 bg-[#E8DCC4] rounded-full hover:bg-[#D6C8A8] transition-colors">
                <User size={14} className="text-[#B14F1C]" />
                <span className="text-xs font-bold text-[#6B5D4F]">{editUser.name}</span>
              </Link>
            )}
            <div className="hidden lg:flex gap-1 bg-[#E8DCC4] p-1">
              <button onClick={() => setLayoutMode('split')} className={`p-1.5  transition-colors ${layoutMode === 'split' ? 'bg-[#E8DCC4]  text-[#B14F1C]' : 'text-[#6B5D4F]'}`}><Columns size={18} /></button>
              <button onClick={() => setLayoutMode('stacked')} className={`p-1.5  transition-colors ${layoutMode === 'stacked' ? 'bg-[#E8DCC4]  text-[#B14F1C]' : 'text-[#6B5D4F]'}`}><Menu size={18} /></button>
            </div>
            <div className="relative">
              <div className="flex items-center">
                <button onClick={toggleBookmark} className={`p-2 rounded-full hover:bg-[#E8DCC4] transition-colors ${isBookmarked ? 'text-[#C4960C]' : 'text-[#1F1A14]'}`} title={isBookmarked ? 'הסר סימניה' : 'הוסף סימניה'}>
                  <Bookmark size={20} fill={isBookmarked ? 'currentColor' : 'none'} />
                </button>
                {bookmarks.length > 0 && (
                  <button onClick={() => setShowBookmarks(!showBookmarks)} className="p-1 rounded-full hover:bg-[#E8DCC4] text-[#6B5D4F] transition-colors" title="הצג סימניות">
                    <ChevronDown size={14} />
                  </button>
                )}
              </div>
              {showBookmarks && bookmarks.length > 0 && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setShowBookmarks(false)} />
                  <div className="absolute left-0 top-full mt-2 z-50 bg-[#E8DCC4] border border-[#D6C8A8] w-72 max-h-80 overflow-y-auto">
                    <div className="p-3 border-b border-[#D6C8A8] flex justify-between items-center">
                      <h4 className="text-sm font-bold text-[#1F1A14]">סימניות ({bookmarks.length})</h4>
                    </div>
                    <div className="p-1">
                      {bookmarks.map(bm => (
                        <Link key={bm.sectionId} href={`/book/${bm.bookId}/${bm.sectionId}`}
                          onClick={() => setShowBookmarks(false)}
                          className={`flex flex-col gap-0.5 px-3 py-2  hover:bg-[#E8DCC4] transition-colors ${bm.sectionId === sectionId ? 'bg-[#E8DCC4]' : ''}`}>
                          <span className="text-sm font-bold text-[#1F1A14] truncate">{bm.title}</span>
                          <span className="text-xs text-[#6B5D4F] truncate">{bm.bookTitle}</span>
                        </Link>
                      ))}
                    </div>
                  </div>
                </>
              )}
            </div>
            <button className="p-2 rounded-full hover:bg-[#E8DCC4] text-[#1F1A14]"><Share2 size={20} /></button>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="flex-grow max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-8" dir="rtl">
        {/* Introduction header - spans full width above blocks */}
        {(section.introduction?.trim() || (!authLoading && canEdit)) && (
          <div className="mb-6">
            {section.introduction?.trim() ? (
              <div className="bg-[#E8DCC4] px-4 py-3 sm:px-6 sm:py-4 border border-[#D6C8A8] text-center">
                <h3 className="text-lg font-bold text-[#B14F1C] font-serif border-b border-[#E8DCC4] pb-2 mb-3">הקדמה</h3>
                <InlineEditor
                  value={section.introduction || ''}
                  onSave={async (newValue) => { await saveSectionField({ introduction: newValue }); }}
                  canEdit={canEdit}
                  minHeight="40px"
                  renderContent={
                    <div className="font-serif leading-loose text-[#2C2A29] text-center text-base">
                      <MarkdownRenderer>{section.introduction}</MarkdownRenderer>
                    </div>
                  }
                />
              </div>
            ) : canEdit && (
              <button
                onClick={async () => { await saveSectionField({ introduction: ' ' }); }}
                className="flex items-center gap-2 px-4 py-2 border border-dashed border-[#D6C8A8] text-[#6B5D4F] hover:text-[#B14F1C] hover:border-[#B14F1C] transition-all text-sm font-bold"
              >
                <Pencil size={14} />
                הוסף הקדמה
              </button>
            )}
          </div>
        )}

        {/* Content blocks */}
        <div ref={containerRef} className="flex flex-col gap-8">
          {blocks.map((block, index) => (
            <div key={block.id}>
              {/* SPLIT MODE (desktop) */}
              {layoutMode === 'split' && (
                <div className="flex flex-col lg:flex-row lg:items-stretch lg:gap-0">
                  {/* Source panel (right side in RTL) - determines row height */}
                  <div className="split-panel" style={{ '--split-width': `${splitPercent}%` } as React.CSSProperties}>
                    <div className="bg-[#F4E3C7] p-6 sm:p-8 border border-[#D6C8A8]">
                      {index === 0 && (
                        <div className="flex justify-between items-start mb-4">
                          <h2 className="text-xl font-bold text-[#B14F1C] font-serif flex items-center gap-2">
                            {isBookmarked && <Bookmark size={18} fill="currentColor" className="shrink-0 text-[#C4960C]" />}
                            מקור
                          </h2>
                          <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border ${section.isEdited ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
                            <span className={`w-2 h-2 rounded-full ${section.isEdited ? 'bg-green-500' : 'bg-red-500'}`}></span>
                            <span className={`text-xs font-bold ${section.isEdited ? 'text-green-700' : 'text-red-700'}`}>{section.isEdited ? 'ערוך' : 'לא ערוך'}</span>
                          </div>
                        </div>
                      )}
                      {block.sourceText ? (
                        <InlineEditor
                          value={block.sourceText}
                          onSave={async (newValue) => { await saveBlockField(block.id, 'sourceText', newValue); }}
                          canEdit={canEdit}
                          minHeight="120px"
                          renderContent={
                            <div className="font-serif leading-loose text-[#2C2A29] text-justify text-lg">
                              <MarkdownRenderer>{block.sourceText}</MarkdownRenderer>
                            </div>
                          }
                        />
                      ) : canEdit ? (
                        <div className="text-center py-8 text-[#6B5D4F] text-sm">טקסט מקור ריק — לחץ לעריכה בעמוד הניהול</div>
                      ) : null}
                      {canEdit && blocks.length > 1 && (
                        <div className="flex justify-end mt-3 pt-3 border-t border-[#D6C8A8]">
                          <button onClick={() => handleDeleteBlock(block.id)} className="text-xs text-[#6B5D4F] hover:text-red-600 transition-colors flex items-center gap-1">
                            <Trash2 size={12} /> מחק קטע
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Drag handle (first block) / spacer (others) */}
                  {index === 0 ? (
                    <div
                      className="hidden lg:flex items-center justify-center w-4 cursor-col-resize group shrink-0 select-none"
                      onMouseDown={handleDragStart}
                      onTouchStart={handleDragStart}
                      title="גרור לשינוי גודל"
                    >
                      <div className="w-1 h-16 rounded-full bg-[#D6C8A8] group-hover:bg-[#B14F1C] group-active:bg-[#B14F1C] transition-colors" />
                    </div>
                  ) : (
                    <div className="hidden lg:block w-4 shrink-0" />
                  )}

                  {/* Commentary panel (left side in RTL) - scrolls within source height */}
                  <div className="flex-1 min-w-0 lg:relative">
                    <div className="bg-[#E8DCC4] p-6 sm:p-8 border border-[#D6C8A8] lg:absolute lg:inset-0 lg:overflow-y-auto custom-scrollbar">
                      {index === 0 && (
                        <h3 className="text-xl font-bold text-[#B14F1C] font-serif border-b border-[#E8DCC4] pb-4 mb-6">ביאורים והרחבות</h3>
                      )}
                      {block.commentaryText ? (
                        <InlineEditor
                          value={block.commentaryText}
                          onSave={async (newValue) => { await saveBlockField(block.id, 'commentaryText', newValue); }}
                          canEdit={canEdit}
                          minHeight="120px"
                          renderContent={
                            <div className="text-base leading-relaxed text-[#1F1A14] text-justify">
                              <SimpleMarkdown>{block.commentaryText}</SimpleMarkdown>
                            </div>
                          }
                        />
                      ) : canEdit ? (
                        <div className="text-center py-8 text-[#6B5D4F] text-sm">ביאור ריק — לחץ לעריכה בעמוד הניהול</div>
                      ) : null}
                    </div>
                  </div>
                </div>
              )}

              {/* STACKED MODE (desktop) + MOBILE */}
              {layoutMode === 'stacked' && (
                <div className="space-y-4">
                  {/* Source */}
                  {(block.sourceText || canEdit) && (
                    <div className="bg-[#F4E3C7] p-6 sm:p-8 border border-[#D6C8A8]">
                      {index === 0 && (
                        <div className="flex justify-between items-start mb-4">
                          <h2 className="text-xl font-bold text-[#B14F1C] font-serif flex items-center gap-2">
                            {isBookmarked && <Bookmark size={18} fill="currentColor" className="shrink-0 text-[#C4960C]" />}
                            מקור
                          </h2>
                          <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border ${section.isEdited ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
                            <span className={`w-2 h-2 rounded-full ${section.isEdited ? 'bg-green-500' : 'bg-red-500'}`}></span>
                            <span className={`text-xs font-bold ${section.isEdited ? 'text-green-700' : 'text-red-700'}`}>{section.isEdited ? 'ערוך' : 'לא ערוך'}</span>
                          </div>
                        </div>
                      )}
                      {block.sourceText ? (
                        <InlineEditor
                          value={block.sourceText}
                          onSave={async (newValue) => { await saveBlockField(block.id, 'sourceText', newValue); }}
                          canEdit={canEdit}
                          minHeight="120px"
                          renderContent={
                            <div className="font-serif leading-loose text-[#2C2A29] text-justify text-xl">
                              <MarkdownRenderer>{block.sourceText}</MarkdownRenderer>
                            </div>
                          }
                        />
                      ) : canEdit ? (
                        <div className="text-center py-8 text-[#6B5D4F] text-sm">טקסט מקור ריק</div>
                      ) : null}
                      {canEdit && blocks.length > 1 && (
                        <div className="flex justify-end mt-3 pt-3 border-t border-[#D6C8A8]">
                          <button onClick={() => handleDeleteBlock(block.id)} className="text-xs text-[#6B5D4F] hover:text-red-600 transition-colors flex items-center gap-1">
                            <Trash2 size={12} /> מחק קטע
                          </button>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Commentary */}
                  {(block.commentaryText || canEdit) && (
                    <div className="bg-[#E8DCC4] p-6 sm:p-8 border border-[#D6C8A8]">
                      {index === 0 && (
                        <h3 className="text-xl font-bold text-[#B14F1C] font-serif border-b border-[#E8DCC4] pb-4 mb-6">ביאורים והרחבות</h3>
                      )}
                      {block.commentaryText ? (
                        <InlineEditor
                          value={block.commentaryText}
                          onSave={async (newValue) => { await saveBlockField(block.id, 'commentaryText', newValue); }}
                          canEdit={canEdit}
                          minHeight="120px"
                          renderContent={
                            <div className="text-base leading-relaxed text-[#1F1A14] text-justify">
                              <SimpleMarkdown>{block.commentaryText}</SimpleMarkdown>
                            </div>
                          }
                        />
                      ) : canEdit ? (
                        <div className="text-center py-8 text-[#6B5D4F] text-sm">ביאור ריק</div>
                      ) : null}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}

          {/* Add block button (editors only) */}
          {canEdit && (
            <button onClick={handleAddBlock}
              className="flex items-center gap-2 justify-center w-full py-4 border-2 border-dashed border-[#B14F1C]/30 text-[#B14F1C] hover:bg-[#B14F1C]/5 hover:border-[#B14F1C] transition-all text-sm font-bold">
              <Plus size={18} /> הוסף זוג מקור + ביאור חדש
            </button>
          )}

          {/* Tags */}
          {tagsArray.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {tagsArray.map((tag: string) => (
                <span key={tag} className="px-3 py-1 bg-[#E8DCC4] text-[#6B5A4E] text-sm rounded-full">#{tag}</span>
              ))}
            </div>
          )}
        </div>

        {/* YouTube Playlist */}
        <div className="mt-8">
          <YouTubePlaylist
            sectionId={sectionId}
            videos={section.youtubeVideos || []}
            canEdit={canEdit}
            onUpdate={(updated: YouTubeVideo[]) => setSection({ ...section, youtubeVideos: updated })}
          />
        </div>

        {/* Comments */}
        <div className="mt-8 bg-[#E8DCC4] p-4 sm:p-5 border border-[#D6C8A8]">
          <h3 className="text-lg font-bold text-[#1F1A14] mb-4 flex items-center gap-2">
            <MessageCircle size={20} className="text-[#B14F1C]" />
            בית מדרש - שאלות ותשובות
          </h3>
          <div className="space-y-4">
            {(section.comments || []).map((comment: any) => (
              <div key={comment.id} className="space-y-3">
                <div className="bg-[#F1E6D2] p-3">
                  <div className="flex justify-between items-center mb-2">
                    <span className="font-bold text-[#1F1A14]">{comment.author}</span>
                    <div className="flex items-center gap-2">
                      {comment.editedAt && <span className="text-xs text-[#6B5D4F]">(נערך {comment.editedAt})</span>}
                      <span className="text-xs text-[#6B5D4F]">{comment.date}</span>
                    </div>
                  </div>
                  {editingCommentId === comment.id ? (
                    <div>
                      <textarea value={editCommentText} onChange={(e) => setEditCommentText(e.target.value)}
                        className="w-full p-3 border border-[#D6C8A8] bg-[#E8DCC4] focus:border-[#B14F1C] outline-none resize-none font-serif" rows={3} />
                      <div className="flex gap-2 mt-2">
                        <button onClick={() => saveCommentEdit(comment.id)} disabled={isSavingComment}
                          className="flex items-center gap-1 px-3 py-1.5 text-xs font-bold bg-[#B14F1C] text-white hover:bg-[#7A2525] disabled:opacity-50">
                          {isSavingComment ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />} שמור
                        </button>
                        <button onClick={() => setEditingCommentId(null)}
                          className="flex items-center gap-1 px-3 py-1.5 text-xs font-bold bg-[#E8DCC4] text-[#1F1A14] hover:bg-[#D6C8A8]">
                          <X size={12} /> ביטול
                        </button>
                      </div>
                    </div>
                  ) : (
                    <p className="text-[#1F1A14]">{comment.text}</p>
                  )}
                  {canManageComments && editingCommentId !== comment.id && (
                    <div className="flex gap-1 mt-2">
                      <button onClick={() => { setReplyingToId(comment.id); setReplyText(''); }}
                        className="flex items-center gap-1 px-2.5 py-1 border border-[#D6C8A8] text-[#6B5D4F] hover:text-[#B14F1C] hover:border-[#B14F1C] transition-all text-xs font-bold">
                        <Reply size={12} /> השב
                      </button>
                      <button onClick={() => { setEditingCommentId(comment.id); setEditCommentText(comment.text); }}
                        className="flex items-center gap-1 px-2.5 py-1 border border-[#D6C8A8] text-[#6B5D4F] hover:text-[#B14F1C] hover:border-[#B14F1C] transition-all text-xs font-bold">
                        <Pencil size={12} /> ערוך
                      </button>
                      <button onClick={() => deleteComment(comment.id)} disabled={isSavingComment}
                        className="flex items-center gap-1 px-2.5 py-1 border border-[#D6C8A8] text-[#6B5D4F] hover:text-red-600 hover:border-red-400 transition-all text-xs font-bold">
                        <Trash2 size={12} /> מחק
                      </button>
                    </div>
                  )}
                  {replyingToId === comment.id && (
                    <div className="mt-3 pt-3 border-t border-[#D6C8A8]">
                      <textarea value={replyText} onChange={(e) => setReplyText(e.target.value)}
                        className="w-full p-3 border border-[#D6C8A8] bg-[#E8DCC4] focus:border-[#B14F1C] outline-none resize-none" rows={2} placeholder="הכנס תשובה..." />
                      <div className="flex gap-2 mt-2">
                        <button onClick={() => submitReply(comment.id)} disabled={isSavingComment}
                          className="flex items-center gap-1 px-3 py-1.5 text-xs font-bold bg-[#B14F1C] text-white hover:bg-[#7A2525] disabled:opacity-50">
                          {isSavingComment ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />} שלח תשובה
                        </button>
                        <button onClick={() => setReplyingToId(null)}
                          className="flex items-center gap-1 px-3 py-1.5 text-xs font-bold bg-[#E8DCC4] text-[#1F1A14] hover:bg-[#D6C8A8]">
                          <X size={12} /> ביטול
                        </button>
                      </div>
                    </div>
                  )}
                </div>
                {comment.replies?.length > 0 && (
                  <div className="mr-4 pr-4 border-r-2 border-[#D6C8A8] space-y-3">
                    {comment.replies.map((reply: any) => (
                      <div key={reply.id} className="bg-[#E8DCC4] p-3">
                        <div className="flex justify-between items-center mb-2">
                          <span className="font-bold text-[#B14F1C]">{reply.author}</span>
                          <span className="text-xs text-[#6B5D4F]">{reply.date}</span>
                        </div>
                        {reply.text && (
                          <div className="text-[#1F1A14]">
                            <SimpleMarkdown>{reply.text}</SimpleMarkdown>
                          </div>
                        )}
                        {reply.audioUrl && (
                          <div className="mt-2">
                            <AudioPlayer src={reply.audioUrl} />
                          </div>
                        )}
                        {reply.attachments?.length > 0 && (
                          <div className="mt-2 flex flex-wrap gap-2">
                            {reply.attachments.map((att: any, i: number) => (
                              att.type === 'image' ? (
                                <a key={i} href={att.url} target="_blank" rel="noopener noreferrer" className="block">
                                  <img src={att.url} alt={att.name} className="max-w-[200px] max-h-[150px] border border-[#D6C8A8] object-cover hover:opacity-90 transition-opacity" />
                                </a>
                              ) : (
                                <a key={i} href={att.url} target="_blank" rel="noopener noreferrer"
                                  className="flex items-center gap-1.5 px-2.5 py-1.5 bg-[#E8DCC4] border border-[#D6C8A8] text-xs text-[#1F1A14] hover:bg-[#F1E6D2] transition-colors">
                                  {att.type === 'pdf' ? '📄' : '📝'}
                                  <span className="font-bold max-w-[150px] truncate">{att.name}</span>
                                </a>
                              )
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="mt-5 pt-4 border-t border-[#D6C8A8]">
            <input type="text" value={newCommentAuthor} onChange={(e) => setNewCommentAuthor(e.target.value)}
              className="w-full sm:w-1/3 p-2.5 border border-[#D6C8A8] bg-[#F1E6D2] focus:border-[#B14F1C] outline-none mb-3 text-sm" placeholder="השם שלך" />
            <textarea value={newCommentText} onChange={(e) => setNewCommentText(e.target.value)}
              className="w-full p-3 border border-[#D6C8A8] bg-[#F1E6D2] focus:border-[#B14F1C] outline-none resize-none text-sm" rows={3} placeholder="הוסף שאלה או הערה..." />
            <div className="flex justify-end mt-3">
              <button onClick={submitComment} disabled={isSubmittingComment}
                className={`px-6 py-2 rounded-full font-medium flex items-center gap-2 ${isSubmittingComment ? 'bg-[#D6C8A8] text-[#6B5D4F] cursor-not-allowed' : 'bg-[#1F1A14] text-white hover:bg-[#3A2B22]'}`}>
                {isSubmittingComment && <Loader2 size={16} className="animate-spin" />}
                {isSubmittingComment ? 'שולח...' : 'פרסם תגובה'}
              </button>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <div className="flex justify-between items-center mt-6">
          {prevSection ? (
            <Link href={`/book/${bookId}/${prevSection.id}`} className="flex items-center gap-2 text-[#B14F1C] font-bold hover:underline">
              <ChevronRight size={18} /> {prevSection.title}
            </Link>
          ) : <div />}
          {nextSection ? (
            <Link href={`/book/${bookId}/${nextSection.id}`} className="flex items-center gap-2 text-[#B14F1C] font-bold hover:underline">
              {nextSection.title} <ChevronLeft size={18} />
            </Link>
          ) : <div />}
        </div>
      </main>
    </div>
  );
}
