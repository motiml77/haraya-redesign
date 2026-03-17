'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { Share2, MessageCircle, Columns, Menu, Bookmark, BookOpen, ChevronDown, ChevronUp, ChevronLeft, ChevronRight, Loader2, User, Pencil, Trash2, Check, X, Reply, FileText } from 'lucide-react';
import { MarkdownRenderer, SimpleMarkdown } from '@/components/MarkdownRenderer';
import { Breadcrumb } from '@/components/Breadcrumb';
import { InlineEditor } from '@/components/InlineEditor';
import { useEditAuth } from '@/hooks/use-edit-auth';
import { authFetch } from '@/lib/auth-fetch';

// Lazy-load CommentaryManager — it's below the fold and has its own heavy dependencies
const CommentaryManager = dynamic(
  () => import('@/components/CommentaryManager').then(m => m.CommentaryManager),
  { loading: () => <div className="animate-pulse bg-[#FAF8F5] rounded-xl h-32" /> }
);

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
  const [isBookMode, setIsBookMode] = useState(false);
  
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

  const { user: editUser, canEdit } = useEditAuth();
  const bookContainerRef = useRef<HTMLDivElement>(null);
  const bookPageRef = useRef(0);

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

  const scrollBook = (direction: 'next' | 'prev') => {
    if (!bookContainerRef.current) return;
    const container = bookContainerRef.current;
    const pageWidth = container.clientWidth;
    // The gap between columns means each page boundary crosses one extra gap
    const gap = parseFloat(getComputedStyle(container).columnGap) || 0;
    const scrollPerPage = pageWidth + gap;
    const maxScroll = container.scrollWidth - pageWidth;
    const maxPages = Math.max(0, Math.round(maxScroll / scrollPerPage));
    const newPage = direction === 'next'
      ? Math.min(bookPageRef.current + 1, maxPages)
      : Math.max(bookPageRef.current - 1, 0);
    bookPageRef.current = newPage;
    // RTL: page 0 = scrollLeft 0, clamp to max scrollable distance
    const target = Math.min(newPage * scrollPerPage, maxScroll);
    container.scrollTo({ left: -target, behavior: 'smooth' });
  };

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
  if (!section.originalText && book?.sections) {
    const children = book.sections
      .filter((s: any) => s.parentId === sectionId)
      .sort((a: any, b: any) => (a.orderIndex || 0) - (b.orderIndex || 0));

    return (
      <div className="min-h-screen bg-[#FAF8F5] font-sans" dir="rtl">
        <header className="bg-white border-b border-[#E5E0D8] py-6 px-6">
          <div className="max-w-4xl mx-auto flex items-start gap-4">
            <Link href="/" className="p-2 rounded-full hover:bg-[#F0EBE1] transition-colors mt-1 shrink-0" title="חזרה לדף הראשי">
              <BookOpen size={28} className="text-[#8C2B2B]" />
            </Link>
            <div className="flex-1">
              <Breadcrumb items={breadcrumbItems} />
              <h1 className="text-3xl font-serif font-bold text-[#4A3B32] mt-4">{section.title}</h1>
            </div>
          </div>
        </header>

        <main className="max-w-4xl mx-auto px-6 py-8">
          {children.length > 0 ? (
            <div className="space-y-3">
              {children.map((child: any) => (
                <Link key={child.id} href={`/book/${bookId}/${child.id}`}
                  className="flex items-center gap-4 bg-white p-5 rounded-2xl shadow-sm border border-[#E5E0D8] hover:border-[#8C2B2B] hover:shadow-md transition-all group">
                  <div className="flex items-center gap-3 flex-1">
                    <FileText size={20} className="text-[#8C7A6B] group-hover:text-[#8C2B2B] transition-colors" />
                    <span className="font-bold text-[#4A3B32]">{child.title}</span>
                  </div>
                  {child.hasContent && (
                    <span className={`w-2.5 h-2.5 rounded-full ${child.isEdited ? 'bg-green-500' : 'bg-red-400'}`}
                      title={child.isEdited ? 'ערוך' : 'לא ערוך'}></span>
                  )}
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-center text-[#8C7A6B] py-12">אין תוכן בחלק זה.</p>
          )}
        </main>
      </div>
    );
  }

  const tagsArray = Array.isArray(section.tags) ? section.tags : (typeof section.tags === 'string' ? section.tags.split(',').map((t: string) => t.trim()).filter(Boolean) : []);

  return (
    <div className="min-h-screen flex flex-col font-sans bg-[#FAF8F5]">
      {/* Header */}
      <header className="bg-white border-b border-[#E5E0D8] py-4 px-6 sticky top-0 z-50 shadow-sm" dir="rtl">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <div className="flex items-start gap-3">
            <Link href="/" className="p-2 rounded-full hover:bg-[#F0EBE1] transition-colors mt-0.5 shrink-0" title="חזרה לדף הראשי">
              <BookOpen size={28} className="text-[#8C2B2B]" />
            </Link>
            <div>
              <Breadcrumb items={breadcrumbItems} />
              <h1 className="text-2xl font-serif font-bold text-[#4A3B32] mt-1">{section.title}</h1>
            </div>
          </div>
          <div className="flex gap-3 items-center">
            {editUser && (
              <Link href="/admin" className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 bg-[#F0EBE1] rounded-full hover:bg-[#E5E0D8] transition-colors">
                <User size={14} className="text-[#8C2B2B]" />
                <span className="text-xs font-bold text-[#8C7A6B]">{editUser.name}</span>
              </Link>
            )}
            <div className="hidden lg:flex gap-1 bg-[#F0EBE1] p-1 rounded-lg">
              <button onClick={() => setLayoutMode('split')} className={`p-1.5 rounded-md transition-colors ${layoutMode === 'split' ? 'bg-white shadow-sm text-[#8C2B2B]' : 'text-[#8C7A6B]'}`}><Columns size={18} /></button>
              <button onClick={() => setLayoutMode('stacked')} className={`p-1.5 rounded-md transition-colors ${layoutMode === 'stacked' ? 'bg-white shadow-sm text-[#8C2B2B]' : 'text-[#8C7A6B]'}`}><Menu size={18} /></button>
            </div>
            <div className="relative">
              <div className="flex items-center">
                <button onClick={toggleBookmark} className={`p-2 rounded-full hover:bg-[#F0EBE1] transition-colors ${isBookmarked ? 'text-[#C4960C]' : 'text-[#4A3B32]'}`} title={isBookmarked ? 'הסר סימניה' : 'הוסף סימניה'}>
                  <Bookmark size={20} fill={isBookmarked ? 'currentColor' : 'none'} />
                </button>
                {bookmarks.length > 0 && (
                  <button onClick={() => setShowBookmarks(!showBookmarks)} className="p-1 rounded-full hover:bg-[#F0EBE1] text-[#8C7A6B] transition-colors" title="הצג סימניות">
                    <ChevronDown size={14} />
                  </button>
                )}
              </div>
              {showBookmarks && bookmarks.length > 0 && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setShowBookmarks(false)} />
                  <div className="absolute left-0 top-full mt-2 z-50 bg-white rounded-xl shadow-xl border border-[#E5E0D8] w-72 max-h-80 overflow-y-auto">
                    <div className="p-3 border-b border-[#E5E0D8] flex justify-between items-center">
                      <h4 className="text-sm font-bold text-[#4A3B32]">סימניות ({bookmarks.length})</h4>
                    </div>
                    <div className="p-1">
                      {bookmarks.map(bm => (
                        <Link key={bm.sectionId} href={`/book/${bm.bookId}/${bm.sectionId}`}
                          onClick={() => setShowBookmarks(false)}
                          className={`flex flex-col gap-0.5 px-3 py-2 rounded-lg hover:bg-[#F0EBE1] transition-colors ${bm.sectionId === sectionId ? 'bg-[#F0EBE1]' : ''}`}>
                          <span className="text-sm font-bold text-[#4A3B32] truncate">{bm.title}</span>
                          <span className="text-xs text-[#8C7A6B] truncate">{bm.bookTitle}</span>
                        </Link>
                      ))}
                    </div>
                  </div>
                </>
              )}
            </div>
            <button className="p-2 rounded-full hover:bg-[#F0EBE1] text-[#4A3B32]"><Share2 size={20} /></button>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="flex-grow max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-8" dir="rtl">
        <div ref={containerRef} className={`flex flex-col gap-8 ${layoutMode === 'split' ? 'lg:flex-row lg:gap-0' : ''}`}>
          {/* Original Text */}
          <div className={layoutMode === 'split' ? '' : 'w-full'} style={layoutMode === 'split' ? { width: `${splitPercent}%` } : undefined}>
            <div className={`${layoutMode === 'split' ? 'lg:sticky lg:top-28 max-h-[calc(100vh-8rem)] overflow-y-auto custom-scrollbar' : ''} bg-[#EDEAE5] p-6 sm:p-8 rounded-2xl shadow-sm border border-[#D5D0C8]`}>
              <div className="flex justify-between items-start mb-4">
                <h2 className="text-xl font-bold text-[#8C2B2B] font-serif flex items-center gap-2">
                  {isBookmarked && <Bookmark size={18} fill="currentColor" className="shrink-0 text-[#C4960C]" />}
                  {section.title}
                </h2>
                <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border ${section.isEdited ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
                  <span className={`w-2 h-2 rounded-full ${section.isEdited ? 'bg-green-500' : 'bg-red-500'}`}></span>
                  <span className={`text-xs font-bold ${section.isEdited ? 'text-green-700' : 'text-red-700'}`}>{section.isEdited ? 'ערוך' : 'לא ערוך'}</span>
                </div>
              </div>
              <InlineEditor
                value={section.originalText || ''}
                onSave={async (newValue) => { await saveSectionField({ originalText: newValue }); }}
                canEdit={canEdit}
                minHeight="200px"
                renderContent={
                  <div className={`font-serif leading-loose text-[#2C2A29] text-justify ${layoutMode === 'split' ? 'text-lg' : 'text-xl'}`}>
                    <MarkdownRenderer>{section.originalText}</MarkdownRenderer>
                  </div>
                }
              />
              <div className="mt-8 pt-6 border-t border-[#F0EBE1] flex flex-wrap gap-2">
                {tagsArray.map((tag: string) => (
                  <span key={tag} className="px-3 py-1 bg-[#F0EBE1] text-[#6B5A4E] text-sm rounded-full">#{tag}</span>
                ))}
              </div>
            </div>
          </div>

          {/* Drag Handle */}
          {layoutMode === 'split' && (
            <div
              className="hidden lg:flex items-center justify-center w-4 cursor-col-resize group shrink-0 select-none"
              onMouseDown={handleDragStart}
              onTouchStart={handleDragStart}
              title="גרור לשינוי גודל"
            >
              <div className="w-1 h-16 rounded-full bg-[#E5E0D8] group-hover:bg-[#8C2B2B] group-active:bg-[#8C2B2B] transition-colors" />
            </div>
          )}

          {/* Commentary + Comments */}
          <div className={`${layoutMode === 'split' ? 'flex-1 min-w-0' : 'w-full'} flex flex-col gap-6`}>
            <div className="lg:hidden flex justify-between items-center bg-white p-4 rounded-xl shadow-sm border border-[#E5E0D8]" onClick={() => setIsMobileCommentaryOpen(!isMobileCommentaryOpen)}>
              <h3 className="text-lg font-bold text-[#8C2B2B]">ביאורים והרחבות</h3>
              {isMobileCommentaryOpen ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
            </div>

            <div className={`flex-col gap-6 ${isMobileCommentaryOpen ? 'flex' : 'hidden lg:flex'}`}>
              <div className="bg-white p-6 sm:p-8 rounded-2xl shadow-sm border border-[#E5E0D8]">
                <div className="flex justify-between items-center border-b border-[#F0EBE1] pb-4 mb-6">
                  <h3 className="text-xl font-bold text-[#8C2B2B] font-serif hidden lg:block">ביאורים והרחבות</h3>
                  <button onClick={() => { bookPageRef.current = 0; setIsBookMode(!isBookMode); }}
                    className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold transition-colors mr-auto ${isBookMode ? 'bg-[#8C2B2B] text-white' : 'bg-[#F0EBE1] text-[#4A3B32] hover:bg-[#E5E0D8]'}`}>
                    <BookOpen size={18} />
                    {isBookMode ? 'חזור לתצוגה רגילה' : 'תצוגת ספר'}
                  </button>
                </div>

                {isBookMode ? (
                  <div className="relative bg-[#FAF8F5] border border-[#E5E0D8] rounded-2xl p-2 sm:p-6 group/book">
                    <button onClick={() => scrollBook('prev')} className="absolute right-2 top-1/2 -translate-y-1/2 z-10 bg-white/90 shadow-md rounded-full p-2 text-[#8C2B2B] opacity-0 group-hover/book:opacity-90 transition-opacity duration-200"><ChevronRight size={24} /></button>
                    <button onClick={() => scrollBook('next')} className="absolute left-2 top-1/2 -translate-y-1/2 z-10 bg-white/90 shadow-md rounded-full p-2 text-[#8C2B2B] opacity-0 group-hover/book:opacity-90 transition-opacity duration-200"><ChevronLeft size={24} /></button>
                    <CommentaryManager
                      commentaries={section.commentary || []}
                      canEdit={canEdit}
                      onSave={async (updated) => { await saveSectionField({ commentary: updated }); }}
                      isBookMode={true}
                      bookContainerRef={bookContainerRef}
                    />
                  </div>
                ) : (
                  <CommentaryManager
                    commentaries={section.commentary || []}
                    canEdit={canEdit}
                    onSave={async (updated) => { await saveSectionField({ commentary: updated }); }}
                    isBookMode={false}
                  />
                )}
              </div>
            </div>

            {/* Comments */}
            <div className="mt-5 bg-white p-4 sm:p-5 rounded-2xl shadow-sm border border-[#E5E0D8]">
              <h3 className="text-lg font-bold text-[#4A3B32] mb-4 flex items-center gap-2">
                <MessageCircle size={20} className="text-[#8C2B2B]" />
                בית מדרש - שאלות ותשובות
              </h3>
              <div className="space-y-4">
                {(section.comments || []).map((comment: any) => (
                  <div key={comment.id} className="space-y-3">
                    <div className="bg-[#FAF8F5] p-3 rounded-xl">
                      <div className="flex justify-between items-center mb-2">
                        <span className="font-bold text-[#4A3B32]">{comment.author}</span>
                        <div className="flex items-center gap-2">
                          {comment.editedAt && <span className="text-xs text-[#8C7A6B]">(נערך {comment.editedAt})</span>}
                          <span className="text-xs text-[#8C7A6B]">{comment.date}</span>
                        </div>
                      </div>
                      {editingCommentId === comment.id ? (
                        <div>
                          <textarea value={editCommentText} onChange={(e) => setEditCommentText(e.target.value)}
                            className="w-full p-3 rounded-xl border border-[#E5E0D8] bg-white focus:ring-2 focus:ring-[#8C2B2B] outline-none resize-none font-serif" rows={3} />
                          <div className="flex gap-2 mt-2">
                            <button onClick={() => saveCommentEdit(comment.id)} disabled={isSavingComment}
                              className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-bold bg-[#8C2B2B] text-white hover:bg-[#7A2525] disabled:opacity-50">
                              {isSavingComment ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />} שמור
                            </button>
                            <button onClick={() => setEditingCommentId(null)}
                              className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-bold bg-[#F0EBE1] text-[#4A3B32] hover:bg-[#E5E0D8]">
                              <X size={12} /> ביטול
                            </button>
                          </div>
                        </div>
                      ) : (
                        <p className="text-[#4A3B32]">{comment.text}</p>
                      )}
                      {canManageComments && editingCommentId !== comment.id && (
                        <div className="flex gap-1 mt-2">
                          <button onClick={() => { setReplyingToId(comment.id); setReplyText(''); }}
                            className="flex items-center gap-1 px-2.5 py-1 rounded-lg border border-[#E5E0D8] text-[#8C7A6B] hover:text-[#8C2B2B] hover:border-[#8C2B2B] transition-all text-xs font-bold">
                            <Reply size={12} /> השב
                          </button>
                          <button onClick={() => { setEditingCommentId(comment.id); setEditCommentText(comment.text); }}
                            className="flex items-center gap-1 px-2.5 py-1 rounded-lg border border-[#E5E0D8] text-[#8C7A6B] hover:text-[#8C2B2B] hover:border-[#8C2B2B] transition-all text-xs font-bold">
                            <Pencil size={12} /> ערוך
                          </button>
                          <button onClick={() => deleteComment(comment.id)} disabled={isSavingComment}
                            className="flex items-center gap-1 px-2.5 py-1 rounded-lg border border-[#E5E0D8] text-[#8C7A6B] hover:text-red-600 hover:border-red-400 transition-all text-xs font-bold">
                            <Trash2 size={12} /> מחק
                          </button>
                        </div>
                      )}
                      {replyingToId === comment.id && (
                        <div className="mt-3 pt-3 border-t border-[#E5E0D8]">
                          <textarea value={replyText} onChange={(e) => setReplyText(e.target.value)}
                            className="w-full p-3 rounded-xl border border-[#E5E0D8] bg-white focus:ring-2 focus:ring-[#8C2B2B] outline-none resize-none" rows={2} placeholder="הכנס תשובה..." />
                          <div className="flex gap-2 mt-2">
                            <button onClick={() => submitReply(comment.id)} disabled={isSavingComment}
                              className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-bold bg-[#8C2B2B] text-white hover:bg-[#7A2525] disabled:opacity-50">
                              {isSavingComment ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />} שלח תשובה
                            </button>
                            <button onClick={() => setReplyingToId(null)}
                              className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-bold bg-[#F0EBE1] text-[#4A3B32] hover:bg-[#E5E0D8]">
                              <X size={12} /> ביטול
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                    {comment.replies?.length > 0 && (
                      <div className="mr-4 pr-4 border-r-2 border-[#E5E0D8] space-y-3">
                        {comment.replies.map((reply: any) => (
                          <div key={reply.id} className="bg-[#F0EBE1] p-3 rounded-xl">
                            <div className="flex justify-between items-center mb-2">
                              <span className="font-bold text-[#8C2B2B]">{reply.author}</span>
                              <span className="text-xs text-[#8C7A6B]">{reply.date}</span>
                            </div>
                            <div className="text-[#4A3B32]">
                              <SimpleMarkdown>{reply.text}</SimpleMarkdown>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>

              <div className="mt-5 pt-4 border-t border-[#E5E0D8]">
                <input type="text" value={newCommentAuthor} onChange={(e) => setNewCommentAuthor(e.target.value)}
                  className="w-full sm:w-1/3 p-2.5 rounded-xl border border-[#E5E0D8] bg-[#FAF8F5] focus:ring-2 focus:ring-[#8C2B2B] outline-none mb-3 text-sm" placeholder="השם שלך" />
                <textarea value={newCommentText} onChange={(e) => setNewCommentText(e.target.value)}
                  className="w-full p-3 rounded-xl border border-[#E5E0D8] bg-[#FAF8F5] focus:ring-2 focus:ring-[#8C2B2B] outline-none resize-none text-sm" rows={3} placeholder="הוסף שאלה או הערה..." />
                <div className="flex justify-end mt-3">
                  <button onClick={submitComment} disabled={isSubmittingComment}
                    className={`px-6 py-2 rounded-full font-medium flex items-center gap-2 ${isSubmittingComment ? 'bg-[#D5D0C8] text-[#8C7A6B] cursor-not-allowed' : 'bg-[#4A3B32] text-white hover:bg-[#3A2B22]'}`}>
                    {isSubmittingComment && <Loader2 size={16} className="animate-spin" />}
                    {isSubmittingComment ? 'שולח...' : 'פרסם תגובה'}
                  </button>
                </div>
              </div>
            </div>

            {/* Navigation */}
            <div className="flex justify-between items-center mt-4">
              {prevSection ? (
                <Link href={`/book/${bookId}/${prevSection.id}`} className="flex items-center gap-2 text-[#8C2B2B] font-bold hover:underline">
                  <ChevronRight size={18} /> {prevSection.title}
                </Link>
              ) : <div />}
              {nextSection ? (
                <Link href={`/book/${bookId}/${nextSection.id}`} className="flex items-center gap-2 text-[#8C2B2B] font-bold hover:underline">
                  {nextSection.title} <ChevronLeft size={18} />
                </Link>
              ) : <div />}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
