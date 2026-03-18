'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { BookOpen, Plus, ChevronDown, ArrowUp, ArrowDown, Pencil, Trash2, Loader2, FolderPlus, Check, X, Eye, EyeOff } from 'lucide-react';
import { authFetch } from '@/lib/auth-fetch';
import { useAdminUser } from '../admin-context';
import Link from 'next/link';

interface SectionNode {
  id: string;
  title: string;
  bookId: string;
  parentId: string | null;
  depth: number;
  orderIndex: number;
  hasContent: boolean;
  isEdited?: boolean;
  isHidden?: boolean;
  children: SectionNode[];
}

function buildTree(flatSections: any[]): SectionNode[] {
  const map = new Map<string, SectionNode>();
  const roots: SectionNode[] = [];

  // Create nodes
  flatSections.forEach(s => {
    map.set(s.id, { ...s, children: [] });
  });

  // Build tree
  flatSections.forEach(s => {
    const node = map.get(s.id)!;
    if (s.parentId && map.has(s.parentId)) {
      map.get(s.parentId)!.children.push(node);
    } else {
      roots.push(node);
    }
  });

  // Sort children by orderIndex
  const sortChildren = (nodes: SectionNode[]) => {
    nodes.sort((a, b) => (a.orderIndex || 0) - (b.orderIndex || 0));
    nodes.forEach(n => sortChildren(n.children));
  };
  sortChildren(roots);

  return roots;
}

export default function AdminBooksPage() {
  const { user } = useAdminUser();
  const [books, setBooks] = useState<any[]>([]);
  const [expandedBook, setExpandedBook] = useState<string | null>(null);
  const [bookSections, setBookSections] = useState<SectionNode[]>([]);

  const bookCache = useRef<Map<string, any>>(new Map());

  const [newBookTitle, setNewBookTitle] = useState('');
  const [newSectionTitle, setNewSectionTitle] = useState('');
  const [addingToParent, setAddingToParent] = useState<{ bookId: string; parentId: string | null } | null>(null);

  const [loadingBooks, setLoadingBooks] = useState(true);
  const [loadingBookDetails, setLoadingBookDetails] = useState(false);
  const [creatingBook, setCreatingBook] = useState(false);
  const [creatingSection, setCreatingSection] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');

  const isAdmin = user?.role === 'admin';

  useEffect(() => { loadBooks(); }, []);

  const loadBooks = (bustCache = false) => {
    setLoadingBooks(true);
    const url = bustCache ? `/api/books?t=${Date.now()}` : '/api/books';
    fetch(url, bustCache ? { cache: 'no-store' } : undefined).then(r => r.json()).then(data => {
      setBooks(data);
      setLoadingBooks(false);
      // Book details are loaded on-demand when expanded (not pre-fetched)
    }).catch(() => setLoadingBooks(false));
  };

  const loadBookDetails = useCallback(async (bookId: string, forceRefresh = false) => {
    if (!forceRefresh && bookCache.current.has(bookId)) {
      const data = bookCache.current.get(bookId);
      setBookSections(buildTree(data.sections || []));
      return;
    }
    setLoadingBookDetails(true);
    try {
      const url = forceRefresh ? `/api/books/${bookId}?t=${Date.now()}` : `/api/books/${bookId}`;
      const res = await fetch(url, forceRefresh ? { cache: 'no-store' } : undefined);
      const data = await res.json();
      if (!data.error) {
        bookCache.current.set(bookId, data);
        setBookSections(buildTree(data.sections || []));
      }
    } catch {}
    setLoadingBookDetails(false);
  }, []);

  const toggleBook = async (bookId: string) => {
    if (expandedBook === bookId) {
      setExpandedBook(null);
      setBookSections([]);
    } else {
      setExpandedBook(bookId);
      await loadBookDetails(bookId);
    }
  };

  const toggleSection = (sectionId: string) => {
    setExpandedSections(prev => {
      const next = new Set(prev);
      if (next.has(sectionId)) next.delete(sectionId);
      else next.add(sectionId);
      return next;
    });
  };

  const createBook = async () => {
    if (!newBookTitle.trim() || creatingBook) return;
    setCreatingBook(true);
    try {
      const res = await authFetch('/api/books', { method: 'POST', body: JSON.stringify({ title: newBookTitle }) });
      if (res.ok) {
        setNewBookTitle('');
        loadBooks(true);
      } else {
        const data = await res.json();
        alert(data.error || 'שגיאה');
      }
    } catch { alert('שגיאה ביצירת ספר'); }
    setCreatingBook(false);
  };

  const createSection = async (bookId: string, parentId: string | null) => {
    if (!newSectionTitle.trim() || creatingSection) return;
    setCreatingSection(true);
    try {
      const res = await authFetch('/api/sections', {
        method: 'POST',
        body: JSON.stringify({ bookId, parentId, title: newSectionTitle }),
      });
      if (res.ok) {
        const { id: newId } = await res.json();
        const title = newSectionTitle;
        setNewSectionTitle('');
        setAddingToParent(null);
        bookCache.current.delete(bookId);

        // Optimistic update: add new section directly to the tree
        const newNode: SectionNode = {
          id: newId, title, bookId, parentId: parentId || null,
          depth: 0, orderIndex: 999, hasContent: false, isEdited: false, isHidden: false, children: [],
        };

        if (parentId) {
          // Add as child of parent
          const addToParent = (nodes: SectionNode[]): SectionNode[] =>
            nodes.map(n => {
              if (n.id === parentId) {
                newNode.depth = n.depth + 1;
                return { ...n, children: [...n.children, newNode] };
              }
              return { ...n, children: addToParent(n.children) };
            });
          setBookSections(prev => addToParent(prev));
          setExpandedSections(prev => new Set(prev).add(parentId));
        } else {
          // Add as top-level
          setBookSections(prev => [...prev, newNode]);
        }
      } else {
        const data = await res.json();
        alert(data.error || 'שגיאה');
      }
    } catch { alert('שגיאה ביצירת חלק'); }
    setCreatingSection(false);
  };

  const deleteItem = async (type: string, id: string, bookId: string, warningMessage?: string) => {
    if (!confirm(warningMessage || 'למחוק?')) return;
    setDeletingId(id);
    try {
      const res = await authFetch(`/api/${type}/${id}`, { method: 'DELETE' });
      if (res.ok) {
        bookCache.current.delete(bookId);
        if (type === 'books') {
          loadBooks(true);
          if (expandedBook === id) {
            setExpandedBook(null);
            setBookSections([]);
          }
        } else {
          await loadBookDetails(bookId, true);
        }
      } else {
        const data = await res.json();
        alert(data.error || 'שגיאה במחיקה');
      }
    } catch { alert('שגיאה במחיקה'); }
    setDeletingId(null);
  };

  const reorderSections = async (bookId: string, parentId: string | null, fromIndex: number, toIndex: number) => {
    // Find siblings
    const findSiblings = (nodes: SectionNode[], targetParentId: string | null): SectionNode[] => {
      if (targetParentId === null) return nodes;
      for (const node of nodes) {
        if (node.id === targetParentId) return node.children;
        const found = findSiblings(node.children, targetParentId);
        if (found.length > 0) return found;
      }
      return [];
    };

    const siblings = parentId === null ? [...bookSections] : findSiblings(bookSections, parentId);
    if (siblings.length === 0) return;

    const items = [...siblings];
    const [moved] = items.splice(fromIndex, 1);
    items.splice(toIndex, 0, moved);

    // Optimistic update
    const updateTree = (nodes: SectionNode[]): SectionNode[] => {
      if (parentId === null) return items;
      return nodes.map(n => {
        if (n.id === parentId) return { ...n, children: items };
        return { ...n, children: updateTree(n.children) };
      });
    };
    setBookSections(parentId === null ? items : updateTree(bookSections));

    try {
      await authFetch('/api/sections/reorder', {
        method: 'PUT',
        body: JSON.stringify({ orderedIds: items.map(s => s.id) }),
      });
      bookCache.current.delete(bookId);
    } catch {
      // Revert on error
      await loadBookDetails(bookId, true);
    }
  };

  const reorderBooks = async (fromIndex: number, toIndex: number) => {
    const items = [...books];
    const [moved] = items.splice(fromIndex, 1);
    items.splice(toIndex, 0, moved);
    // Optimistic update
    setBooks(items);
    try {
      await authFetch('/api/books/reorder', {
        method: 'PUT',
        body: JSON.stringify({ orderedIds: items.map(b => b.id) }),
      });
    } catch {
      loadBooks(true);
    }
  };

  const startRename = (id: string, currentTitle: string) => {
    setEditingId(id);
    setEditingTitle(currentTitle);
  };

  const renameBook = async (bookId: string) => {
    const trimmed = editingTitle.trim();
    if (!trimmed || trimmed === books.find(b => b.id === bookId)?.title) {
      setEditingId(null);
      return;
    }
    // Optimistic update
    setBooks(prev => prev.map(b => b.id === bookId ? { ...b, title: trimmed } : b));
    setEditingId(null);
    // Save to Firebase
    authFetch(`/api/books/${bookId}`, { method: 'PUT', body: JSON.stringify({ title: trimmed }) })
      .then(res => { if (!res.ok) throw new Error(); bookCache.current.delete(bookId); })
      .catch(() => { alert('שגיאה בשינוי שם הספר'); loadBooks(true); });
  };

  const renameSection = async (sectionId: string, bookId: string) => {
    const trimmed = editingTitle.trim();
    if (!trimmed) { setEditingId(null); return; }
    // Optimistic: update tree
    const updateTree = (nodes: SectionNode[]): SectionNode[] =>
      nodes.map(n => ({
        ...n,
        title: n.id === sectionId ? trimmed : n.title,
        children: updateTree(n.children),
      }));
    setBookSections(prev => updateTree(prev));
    setEditingId(null);
    // Save to Firebase
    authFetch(`/api/sections/${sectionId}`, { method: 'PUT', body: JSON.stringify({ title: trimmed }) })
      .then(res => { if (!res.ok) throw new Error(); bookCache.current.delete(bookId); })
      .catch(() => { alert('שגיאה בשינוי שם'); loadBookDetails(bookId, true); });
  };

  const toggleSectionVisibility = (sectionId: string, bookId: string, currentlyHidden: boolean) => {
    const newHidden = !currentlyHidden;
    // Optimistic update
    const updateTree = (nodes: SectionNode[]): SectionNode[] =>
      nodes.map(n => ({
        ...n,
        isHidden: n.id === sectionId ? newHidden : n.isHidden,
        children: updateTree(n.children),
      }));
    setBookSections(prev => updateTree(prev));
    // Save to Firebase
    authFetch(`/api/sections/${sectionId}`, { method: 'PUT', body: JSON.stringify({ isHidden: newHidden }) })
      .then(res => { if (!res.ok) throw new Error(); bookCache.current.delete(bookId); })
      .catch(() => { alert('שגיאה בעדכון נראות'); loadBookDetails(bookId, true); });
  };

  return (
    <div className="space-y-6">
      {/* Create Book - admin only */}
      {isAdmin && (
        <div className="bg-white p-4 rounded-2xl shadow-sm border border-[#E5E0D8]">
          <div className="flex gap-3 items-end">
            <div className="flex-1">
              <label className="block text-sm font-bold text-[#8C7A6B] mb-1">ספר חדש</label>
              <input type="text" value={newBookTitle} onChange={(e) => setNewBookTitle(e.target.value)}
                className="w-full p-2.5 rounded-xl border border-[#E5E0D8] bg-[#FAF8F5] focus:ring-2 focus:ring-[#8C2B2B] outline-none" placeholder="שם הספר..."
                onKeyDown={(e) => e.key === 'Enter' && createBook()} disabled={creatingBook} />
            </div>
            <button onClick={createBook} disabled={creatingBook}
              className="px-4 py-2.5 bg-[#8C2B2B] text-white rounded-xl hover:bg-[#7A2525] transition-colors font-bold flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed">
              {creatingBook ? <Loader2 size={18} className="animate-spin" /> : <Plus size={18} />}
              {creatingBook ? 'יוצר...' : 'צור ספר'}
            </button>
          </div>
        </div>
      )}

      {loadingBooks && (
        <div className="flex items-center justify-center py-8 gap-2 text-[#8C7A6B]">
          <Loader2 size={20} className="animate-spin" />
          <span>טוען ספרים...</span>
        </div>
      )}

      {/* Books list */}
      <div className="space-y-4">
        {books.map((book, bookIndex) => (
          <div key={book.id} className={`bg-white rounded-2xl shadow-sm border border-[#E5E0D8] overflow-hidden ${book.isHidden ? 'opacity-50' : ''}`}>
            <div onClick={() => editingId !== `book-${book.id}` && toggleBook(book.id)}
              className="w-full flex justify-between items-center p-5 hover:bg-[#FAF8F5] transition-colors text-right cursor-pointer">
              <div className="flex items-center gap-3">
                {/* Book reorder buttons */}
                {isAdmin && books.length > 1 && (
                  <div className="flex flex-col items-center" onClick={(e) => e.stopPropagation()}>
                    <button
                      onClick={() => bookIndex > 0 && reorderBooks(bookIndex, bookIndex - 1)}
                      disabled={bookIndex === 0}
                      className="p-0.5 text-[#D5D0C8] hover:text-[#8C2B2B] disabled:opacity-20 disabled:cursor-default transition-colors"
                      title="הזז למעלה"
                    >
                      <ArrowUp size={14} />
                    </button>
                    <button
                      onClick={() => bookIndex < books.length - 1 && reorderBooks(bookIndex, bookIndex + 1)}
                      disabled={bookIndex === books.length - 1}
                      className="p-0.5 text-[#D5D0C8] hover:text-[#8C2B2B] disabled:opacity-20 disabled:cursor-default transition-colors"
                      title="הזז למטה"
                    >
                      <ArrowDown size={14} />
                    </button>
                  </div>
                )}
                <BookOpen size={24} className="text-[#8C2B2B]" />
                {editingId === `book-${book.id}` ? (
                  <input type="text" value={editingTitle} onChange={(e) => setEditingTitle(e.target.value)}
                    onClick={(e) => e.stopPropagation()}
                    onKeyDown={(e) => { if (e.key === 'Enter') renameBook(book.id); if (e.key === 'Escape') setEditingId(null); }}
                    onBlur={() => renameBook(book.id)}
                    className="text-lg font-bold text-[#4A3B32] bg-white border border-[#8C2B2B] rounded-lg px-2 py-0.5 outline-none focus:ring-2 focus:ring-[#8C2B2B]/30"
                    autoFocus />
                ) : (
                  <h3 className="text-lg font-bold text-[#4A3B32]">{book.title}</h3>
                )}
                {editingId !== `book-${book.id}` && (
                  <button onClick={(e) => { e.stopPropagation(); startRename(`book-${book.id}`, book.title); }}
                    className="p-1 text-[#D5D0C8] hover:text-[#8C2B2B] transition-colors rounded" title="שנה שם">
                    <Pencil size={14} />
                  </button>
                )}
              </div>
              <div className="flex items-center gap-2">
                {isAdmin && (
                  <button onClick={(e) => {
                    e.stopPropagation();
                    const newHidden = !book.isHidden;
                    setBooks(prev => prev.map(b => b.id === book.id ? { ...b, isHidden: newHidden } : b));
                    authFetch(`/api/books/${book.id}`, { method: 'PUT', body: JSON.stringify({ isHidden: newHidden }) })
                      .catch(() => { alert('שגיאה בעדכון נראות'); loadBooks(true); });
                  }}
                    className={`p-1.5 rounded-lg transition-colors ${book.isHidden ? 'text-[#D5D0C8] hover:text-[#4A3B32]' : 'text-[#4A3B32] hover:text-[#8C7A6B]'}`}
                    title={book.isHidden ? 'הצג לציבור' : 'הסתר מהציבור'}>
                    {book.isHidden ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                )}
                {isAdmin && (
                  <button onClick={(e) => { e.stopPropagation(); deleteItem('books', book.id, book.id); }}
                    disabled={deletingId === book.id}
                    className="p-1.5 text-red-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50">
                    {deletingId === book.id ? <Loader2 size={16} className="animate-spin" /> : <Trash2 size={16} />}
                  </button>
                )}
                {loadingBookDetails && expandedBook === book.id
                  ? <Loader2 size={20} className="text-[#8C7A6B] animate-spin" />
                  : <ChevronDown size={20} className={`text-[#8C7A6B] transition-transform ${expandedBook === book.id ? 'rotate-180' : ''}`} />
                }
              </div>
            </div>

            {expandedBook === book.id && !loadingBookDetails && (
              <div className="border-t border-[#E5E0D8] p-5 bg-[#FAF8F5] space-y-2">
                {/* Section tree */}
                {bookSections.map((section, index) => (
                  <SectionItem
                    key={section.id}
                    section={section}
                    index={index}
                    siblingCount={bookSections.length}
                    bookId={book.id}
                    isAdmin={isAdmin}
                    expandedSections={expandedSections}
                    onToggle={toggleSection}
                    onDelete={(id, warning) => deleteItem('sections', id, book.id, warning)}
                    deletingId={deletingId}
                    onReorder={(parentId, from, to) => reorderSections(book.id, parentId, from, to)}
                    addingToParent={addingToParent}
                    onStartAdd={(parentId) => { setAddingToParent({ bookId: book.id, parentId }); setNewSectionTitle(''); }}
                    newSectionTitle={newSectionTitle}
                    onNewSectionTitleChange={setNewSectionTitle}
                    onCreateSection={(parentId) => createSection(book.id, parentId)}
                    creatingSection={creatingSection}
                    editingId={editingId}
                    editingTitle={editingTitle}
                    onStartRename={startRename}
                    onEditingTitleChange={setEditingTitle}
                    onRenameSection={renameSection}
                    onCancelRename={() => setEditingId(null)}
                    onToggleVisibility={(id, hidden) => toggleSectionVisibility(id, book.id, hidden)}
                  />
                ))}

                {bookSections.length === 0 && (
                  <p className="text-xs text-[#8C7A6B] text-center py-4">אין תוכן בספר זה</p>
                )}

                {/* Add top-level section */}
                {addingToParent?.bookId === book.id && addingToParent?.parentId === null ? (
                  <div className="flex gap-2 items-center mt-3">
                    <input type="text" value={newSectionTitle} onChange={(e) => setNewSectionTitle(e.target.value)}
                      className="flex-1 p-2 rounded-lg border border-[#E5E0D8] bg-white text-sm" placeholder="שם החלק החדש..."
                      onKeyDown={(e) => { if (e.key === 'Enter') createSection(book.id, null); if (e.key === 'Escape') setAddingToParent(null); }}
                      disabled={creatingSection} autoFocus />
                    <button onClick={() => createSection(book.id, null)} disabled={creatingSection}
                      className="px-3 py-2 bg-[#6B5A4E] text-white rounded-lg text-xs font-bold disabled:opacity-50">
                      {creatingSection ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
                    </button>
                    <button onClick={() => setAddingToParent(null)} className="px-2 py-2 text-[#8C7A6B] hover:text-red-500 text-xs">✕</button>
                  </div>
                ) : (
                  <button onClick={() => { setAddingToParent({ bookId: book.id, parentId: null }); setNewSectionTitle(''); }}
                    className="flex items-center gap-1.5 text-sm text-[#8C7A6B] hover:text-[#8C2B2B] font-bold mt-3 transition-colors">
                    <FolderPlus size={16} /> הוסף חלק ראשי
                  </button>
                )}
              </div>
            )}
          </div>
        ))}

        {!loadingBooks && books.length === 0 && (
          <p className="text-center text-[#8C7A6B] py-12">אין ספרים עדיין. {isAdmin ? 'צור ספר חדש למעלה.' : ''}</p>
        )}
      </div>
    </div>
  );
}

function SectionItem({ section, index, siblingCount, bookId, isAdmin, expandedSections, onToggle, onDelete,
  deletingId, onReorder, addingToParent, onStartAdd, newSectionTitle, onNewSectionTitleChange,
  onCreateSection, creatingSection, editingId, editingTitle, onStartRename, onEditingTitleChange,
  onRenameSection, onCancelRename, onToggleVisibility,
}: {
  section: SectionNode; index: number; siblingCount: number; bookId: string; isAdmin: boolean;
  expandedSections: Set<string>; onToggle: (id: string) => void;
  onDelete: (id: string, warning?: string) => void;
  deletingId: string | null;
  onReorder: (parentId: string | null, fromIndex: number, toIndex: number) => void;
  addingToParent: { bookId: string; parentId: string | null } | null;
  onStartAdd: (parentId: string | null) => void;
  newSectionTitle: string;
  onNewSectionTitleChange: (v: string) => void;
  onCreateSection: (parentId: string | null) => void;
  creatingSection: boolean;
  editingId: string | null;
  editingTitle: string;
  onStartRename: (id: string, currentTitle: string) => void;
  onEditingTitleChange: (v: string) => void;
  onRenameSection: (sectionId: string, bookId: string) => void;
  onCancelRename: () => void;
  onToggleVisibility: (id: string, currentlyHidden: boolean) => void;
}) {
  const hasChildren = section.children.length > 0;
  const isExpanded = expandedSections.has(section.id);
  const isAddingHere = addingToParent?.bookId === bookId && addingToParent?.parentId === section.id;

  const depthColors = ['bg-white', 'bg-[#FAF8F5]', 'bg-[#F5F0EA]', 'bg-[#F0EBE1]'];
  const bgColor = depthColors[Math.min(section.depth, depthColors.length - 1)];

  return (
    <div className={`${bgColor} rounded-xl border border-[#E5E0D8] overflow-hidden ${section.isHidden ? 'opacity-50' : ''}`}>
      <div className="flex items-center gap-1 group">
        {/* Move up/down buttons */}
        <div className="flex flex-col items-center">
          <button
            onClick={() => index > 0 && onReorder(section.parentId, index, index - 1)}
            disabled={index === 0}
            className="p-0.5 text-[#D5D0C8] hover:text-[#8C2B2B] disabled:opacity-20 disabled:cursor-default transition-colors"
            title="הזז למעלה"
          >
            <ArrowUp size={12} />
          </button>
          <button
            onClick={() => index < siblingCount - 1 && onReorder(section.parentId, index, index + 1)}
            disabled={index === siblingCount - 1}
            className="p-0.5 text-[#D5D0C8] hover:text-[#8C2B2B] disabled:opacity-20 disabled:cursor-default transition-colors"
            title="הזז למטה"
          >
            <ArrowDown size={12} />
          </button>
        </div>

        {/* Expand/collapse */}
        <button onClick={() => hasChildren && onToggle(section.id)} className={`p-1 ${hasChildren ? 'cursor-pointer' : 'cursor-default opacity-0'}`}>
          <ChevronDown size={14} className={`text-[#8C7A6B] transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
        </button>

        {/* Title - click navigates to edit page */}
        {editingId === section.id ? (
          <div className="flex-1 flex items-center gap-2 p-2 min-w-0">
            <input type="text" value={editingTitle} onChange={(e) => onEditingTitleChange(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') onRenameSection(section.id, bookId); if (e.key === 'Escape') onCancelRename(); }}
              onBlur={() => onRenameSection(section.id, bookId)}
              className="text-sm font-bold text-[#4A3B32] bg-white border border-[#8C2B2B] rounded-lg px-2 py-0.5 outline-none focus:ring-2 focus:ring-[#8C2B2B]/30 flex-1 min-w-0"
              autoFocus />
          </div>
        ) : (
          <Link href={`/admin/sections/${section.id}`}
            className="flex-1 flex items-center gap-2 p-2 min-w-0 cursor-pointer hover:bg-black/5 rounded transition-colors">
            {section.hasContent && (
              <span className={`w-2 h-2 rounded-full shrink-0 ${section.isEdited ? 'bg-green-500' : 'bg-red-400'}`}></span>
            )}
            <span className="text-sm font-bold text-[#4A3B32] truncate">{section.title}</span>
            {hasChildren && (
              <span className="text-xs text-[#8C7A6B] bg-[#F0EBE1] px-1.5 py-0.5 rounded-full shrink-0">{section.children.length}</span>
            )}
          </Link>
        )}

        {/* Actions */}
        <div className="flex items-center gap-1 shrink-0 px-1">
          <button onClick={() => onToggleVisibility(section.id, !!section.isHidden)}
            className={`p-1.5 rounded transition-colors ${section.isHidden ? 'text-[#D5D0C8] hover:text-[#4A3B32]' : 'text-[#4A3B32] hover:text-[#8C7A6B]'}`}
            title={section.isHidden ? 'הצג לציבור' : 'הסתר מהציבור'}>
            {section.isHidden ? <EyeOff size={14} /> : <Eye size={14} />}
          </button>
          <button onClick={() => onStartRename(section.id, section.title)}
            className="p-1.5 text-[#8C7A6B] hover:text-[#8C2B2B] rounded transition-colors" title="שנה שם">
            <Pencil size={14} />
          </button>
          <button onClick={() => onStartAdd(section.id)}
            className="p-1.5 text-[#8C7A6B] hover:text-[#6B5A4E] rounded transition-colors" title="הוסף תת-חלק">
            <FolderPlus size={14} />
          </button>
          {isAdmin && (
            <button onClick={() => onDelete(section.id, section.children.length > 0
              ? `אזהרה: מחיקת "${section.title}" תמחק גם את כל ${section.children.length} החלקים שבתוכו!\n\nהאם אתה בטוח?`
              : `למחוק את "${section.title}"?`)}
              disabled={deletingId === section.id}
              className="p-1.5 text-red-400 hover:text-red-600 rounded transition-colors disabled:opacity-50">
              {deletingId === section.id ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
            </button>
          )}
        </div>
      </div>

      {/* Children */}
      {isExpanded && hasChildren && (
        <div className="border-t border-[#E5E0D8] p-2 space-y-1.5">
          {section.children.map((child, childIndex) => (
            <SectionItem
              key={child.id}
              section={child}
              index={childIndex}
              siblingCount={section.children.length}
              bookId={bookId}
              isAdmin={isAdmin}
              expandedSections={expandedSections}
              onToggle={onToggle}
              onDelete={onDelete}
              deletingId={deletingId}
              onReorder={onReorder}
              addingToParent={addingToParent}
              onStartAdd={onStartAdd}
              newSectionTitle={newSectionTitle}
              onNewSectionTitleChange={onNewSectionTitleChange}
              onCreateSection={onCreateSection}
              creatingSection={creatingSection}
              editingId={editingId}
              editingTitle={editingTitle}
              onStartRename={onStartRename}
              onEditingTitleChange={onEditingTitleChange}
              onRenameSection={onRenameSection}
              onCancelRename={onCancelRename}
              onToggleVisibility={onToggleVisibility}
            />
          ))}
        </div>
      )}

      {/* Add child form */}
      {isAddingHere && (
        <div className="border-t border-[#E5E0D8] p-2">
          <div className="flex gap-2 items-center">
            <input type="text" value={newSectionTitle} onChange={(e) => onNewSectionTitleChange(e.target.value)}
              className="flex-1 p-2 rounded-lg border border-[#E5E0D8] bg-white text-sm" placeholder="שם החלק החדש..."
              onKeyDown={(e) => { if (e.key === 'Enter') onCreateSection(section.id); if (e.key === 'Escape') onStartAdd('__cancel__' as any); }}
              disabled={creatingSection} autoFocus />
            <button onClick={() => onCreateSection(section.id)} disabled={creatingSection}
              className="px-3 py-2 bg-[#6B5A4E] text-white rounded-lg text-xs font-bold disabled:opacity-50">
              {creatingSection ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
