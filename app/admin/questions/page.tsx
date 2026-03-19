'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { MessageSquare, Bell, ExternalLink, ChevronDown, CheckCircle, Mail, History, Headphones, Trash2, AlertTriangle, Loader2 } from 'lucide-react';
import { BookLoader } from '@/components/BookLoader';
import { authFetch } from '@/lib/auth-fetch';
import { useAdminUser } from '../admin-context';
import { AudioRecorder } from '@/components/AudioRecorder';
import { AudioPlayer } from '@/components/AudioPlayer';
import { storage } from '@/lib/firebase';
import { ref, listAll, deleteObject, getDownloadURL, getMetadata } from 'firebase/storage';

export default function AdminQuestionsPage() {
  const { user } = useAdminUser();
  const [questions, setQuestions] = useState<any[]>([]);
  const [unansweredComments, setUnansweredComments] = useState<any[]>([]);
  const [contactMessages, setContactMessages] = useState<any[]>([]);
  const [replyText, setReplyText] = useState<{ [key: string]: string }>({});
  const [replyAudio, setReplyAudio] = useState<{ [key: string]: string }>({});
  const [isLoading, setIsLoading] = useState(true);
  const [tab, setTab] = useState<'beit-midrash' | 'editor' | 'contact' | 'history' | 'recordings'>('beit-midrash');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // History state
  const [historyQuestions, setHistoryQuestions] = useState<any[]>([]);
  const [historyComments, setHistoryComments] = useState<any[]>([]);
  const [historyContact, setHistoryContact] = useState<any[]>([]);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);

  // Recording management state
  const [recordings, setRecordings] = useState<{ name: string; fullPath: string; url: string; size: number; timeCreated: string; sectionId: string; details: string }[]>([]);
  const [recordingsLoading, setRecordingsLoading] = useState(false);
  const [recordingsLoaded, setRecordingsLoaded] = useState(false);
  const [deletingPath, setDeletingPath] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const isAdmin = user?.role === 'admin';
  const isRabbi = user?.role === 'rabbi';

  const refreshData = () => {
    authFetch('/api/questions')
      .then(res => res.json())
      .then(data => {
        setQuestions(data.questions || []);
        setUnansweredComments(data.unansweredComments || []);
      })
      .catch(() => {});
  };

  const refreshContact = () => {
    authFetch('/api/contact')
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) setContactMessages(data);
      })
      .catch(() => {});
  };

  useEffect(() => {
    Promise.all([
      authFetch('/api/questions').then(res => res.json()).then(data => {
        setQuestions(data.questions || []);
        setUnansweredComments(data.unansweredComments || []);
      }).catch(() => {}),
      authFetch('/api/contact').then(res => res.json()).then(data => {
        if (Array.isArray(data)) setContactMessages(data);
      }).catch(() => {}),
    ]).finally(() => setIsLoading(false));
  }, []);

  // Load history when switching to history tab
  const loadHistory = async () => {
    if (historyLoaded) return;
    setHistoryLoading(true);
    try {
      const [qData, cData] = await Promise.all([
        authFetch('/api/questions?includeResolved=true').then(r => r.json()),
        authFetch('/api/contact?includeResolved=true').then(r => r.json()),
      ]);
      setHistoryQuestions((qData.questions || []).filter((q: any) => q.resolved));
      setHistoryComments(qData.resolvedComments || []);
      setHistoryContact((Array.isArray(cData) ? cData : []).filter((m: any) => m.resolved));
      setHistoryLoaded(true);
    } catch {}
    setHistoryLoading(false);
  };

  // Reply to beit midrash comment
  const handleReplySubmit = async (sectionId: string, commentId: number | string) => {
    const key = `${sectionId}-${commentId}`;
    const text = replyText[key];
    const audio = replyAudio[key];
    if (!text && !audio) return;

    try {
      const sectionRes = await fetch(`/api/sections/${sectionId}`);
      const sectionData = await sectionRes.json();

      const reply: any = { id: Date.now(), author: user?.name || 'הרב המשיב', date: new Date().toISOString().split('T')[0], text: text || '' };
      if (audio) reply.audioUrl = audio;

      const updatedComments = (sectionData.comments || []).map((c: any) => {
        if (c.id === commentId) {
          return { ...c, replies: [...(c.replies || []), reply] };
        }
        return c;
      });

      await authFetch(`/api/sections/${sectionId}`, { method: 'PUT', body: JSON.stringify({ comments: updatedComments }) });
      setReplyText({ ...replyText, [key]: '' });
      setReplyAudio({ ...replyAudio, [key]: '' });
      setUnansweredComments(unansweredComments.filter(c => !(c.sectionId === sectionId && c.id === commentId)));
      setExpandedId(null);
      setHistoryLoaded(false);
    } catch { alert('שגיאה בשליחת התשובה'); }
  };

  // Reply to editor question
  const handleEditorQuestionReply = async (sectionId: string, questionId: number | string) => {
    const key = `editor-${sectionId}-${questionId}`;
    const text = replyText[key];
    const audio = replyAudio[key];
    if (!text && !audio) return;

    try {
      const sectionRes = await fetch(`/api/sections/${sectionId}`);
      const sectionData = await sectionRes.json();

      const reply: any = { id: Date.now(), author: user?.name || 'הרב המשיב', date: new Date().toISOString().split('T')[0], text: text || '' };
      if (audio) reply.audioUrl = audio;

      const updatedQuestions = (sectionData.questionsForRabbi || []).map((q: any) => {
        if (q.id === questionId) {
          return { ...q, replies: [...(q.replies || []), reply] };
        }
        return q;
      });

      await authFetch(`/api/sections/${sectionId}`, { method: 'PUT', body: JSON.stringify({ questionsForRabbi: updatedQuestions }) });
      setReplyText({ ...replyText, [key]: '' });
      setReplyAudio({ ...replyAudio, [key]: '' });
      refreshData();
      setHistoryLoaded(false);
    } catch { alert('שגיאה בשליחת התשובה'); }
  };

  // Reply to contact message
  const handleContactReply = async (messageId: string) => {
    const key = `contact-${messageId}`;
    const text = replyText[key];
    if (!text) return;

    try {
      await authFetch(`/api/contact/${messageId}`, {
        method: 'PUT',
        body: JSON.stringify({ reply: { author: user?.name || 'הרב המשיב', text } }),
      });
      setReplyText({ ...replyText, [key]: '' });
      refreshContact();
      setHistoryLoaded(false);
    } catch { alert('שגיאה בשליחת התשובה'); }
  };

  // Resolve editor question
  const handleResolveQuestion = async (sectionId: string, questionId: number | string) => {
    try {
      const sectionRes = await fetch(`/api/sections/${sectionId}`);
      const sectionData = await sectionRes.json();

      const updatedQuestions = (sectionData.questionsForRabbi || []).map((q: any) => {
        if (q.id === questionId) {
          return { ...q, resolved: true, resolvedBy: user?.name, resolvedDate: new Date().toISOString().split('T')[0] };
        }
        return q;
      });

      await authFetch(`/api/sections/${sectionId}`, { method: 'PUT', body: JSON.stringify({ questionsForRabbi: updatedQuestions }) });
      setQuestions(questions.filter(q => !(q.sectionId === sectionId && q.id === questionId)));
      setHistoryLoaded(false);
    } catch { alert('שגיאה בעדכון סטטוס'); }
  };

  // Resolve beit midrash comment
  const handleResolveComment = async (sectionId: string, commentId: number | string) => {
    try {
      const sectionRes = await fetch(`/api/sections/${sectionId}`);
      const sectionData = await sectionRes.json();

      const updatedComments = (sectionData.comments || []).map((c: any) => {
        if (c.id === commentId) {
          return { ...c, resolved: true, resolvedBy: user?.name, resolvedDate: new Date().toISOString().split('T')[0] };
        }
        return c;
      });

      await authFetch(`/api/sections/${sectionId}`, { method: 'PUT', body: JSON.stringify({ comments: updatedComments }) });
      setUnansweredComments(unansweredComments.filter(c => !(c.sectionId === sectionId && c.id === commentId)));
      setHistoryLoaded(false);
    } catch { alert('שגיאה בעדכון סטטוס'); }
  };

  // Resolve contact message
  const handleResolveContact = async (messageId: string) => {
    try {
      await authFetch(`/api/contact/${messageId}`, {
        method: 'PUT',
        body: JSON.stringify({ resolved: true, resolvedBy: user?.name }),
      });
      setContactMessages(contactMessages.filter(m => m.id !== messageId));
      setHistoryLoaded(false);
    } catch { alert('שגיאה בעדכון סטטוס'); }
  };

  // Load all recordings from Firebase Storage
  const loadRecordings = useCallback(async () => {
    if (recordingsLoaded) return;
    setRecordingsLoading(true);
    try {
      const rootRef = ref(storage, 'audio-replies');
      const rootResult = await listAll(rootRef);

      const allFiles: typeof recordings = [];
      for (const folderRef of rootResult.prefixes) {
        const sectionId = folderRef.name;
        const folderResult = await listAll(folderRef);
        for (const itemRef of folderResult.items) {
          try {
            const [url, metadata] = await Promise.all([
              getDownloadURL(itemRef),
              getMetadata(itemRef),
            ]);
            // Parse filename: reply_{commentId}_{authorName}_{timestamp}.webm
            const parts = itemRef.name.replace('.webm', '').split('_');
            const commentId = parts[1] || '?';
            const authorName = parts[2] || '?';
            allFiles.push({
              name: itemRef.name,
              fullPath: itemRef.fullPath,
              url,
              size: metadata.size,
              timeCreated: metadata.timeCreated,
              sectionId,
              details: `סקשן: ${sectionId} | תגובה: ${commentId} | מחבר: ${authorName}`,
            });
          } catch {}
        }
      }

      allFiles.sort((a, b) => new Date(b.timeCreated).getTime() - new Date(a.timeCreated).getTime());
      setRecordings(allFiles);
      setRecordingsLoaded(true);
    } catch (err) {
      console.error('Error loading recordings:', err);
    }
    setRecordingsLoading(false);
  }, [recordingsLoaded]);

  const deleteRecording = useCallback(async (fullPath: string) => {
    setDeletingPath(fullPath);
    try {
      const fileRef = ref(storage, fullPath);
      await deleteObject(fileRef);
      setRecordings(prev => prev.filter(r => r.fullPath !== fullPath));
      setConfirmDelete(null);
    } catch (err) {
      console.error('Delete error:', err);
      alert('שגיאה במחיקת ההקלטה');
    }
    setDeletingPath(null);
  }, []);

  if (isLoading) return <BookLoader />;

  const sectionLink = (item: any) => {
    if (item.bookId && item.sectionId) return `/book/${item.bookId}/${item.sectionId}`;
    return null;
  };

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  return (
    <div className="space-y-6">
      <div className="flex gap-2 bg-white p-2 rounded-2xl shadow-sm border border-[#E5E0D8] flex-wrap">
        <button onClick={() => setTab('beit-midrash')}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-bold transition-colors flex-1 justify-center min-w-0 ${tab === 'beit-midrash' ? 'bg-[#8C2B2B] text-white' : 'text-[#8C7A6B] hover:bg-[#F0EBE1]'}`}>
          <Bell size={16} /> <span className="truncate">בית מדרש</span>
          {unansweredComments.length > 0 && (
            <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${tab === 'beit-midrash' ? 'bg-white text-[#8C2B2B]' : 'bg-[#8C2B2B] text-white'}`}>{unansweredComments.length}</span>
          )}
        </button>
        <button onClick={() => setTab('editor')}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-bold transition-colors flex-1 justify-center min-w-0 ${tab === 'editor' ? 'bg-[#8C2B2B] text-white' : 'text-[#8C7A6B] hover:bg-[#F0EBE1]'}`}>
          <MessageSquare size={16} /> <span className="truncate">עורכים</span>
          {questions.length > 0 && (
            <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${tab === 'editor' ? 'bg-white text-[#8C2B2B]' : 'bg-[#8C2B2B] text-white'}`}>{questions.length}</span>
          )}
        </button>
        {isAdmin && (
          <button onClick={() => setTab('contact')}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-bold transition-colors flex-1 justify-center min-w-0 ${tab === 'contact' ? 'bg-[#8C2B2B] text-white' : 'text-[#8C7A6B] hover:bg-[#F0EBE1]'}`}>
            <Mail size={16} /> <span className="truncate">צור קשר</span>
            {contactMessages.length > 0 && (
              <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${tab === 'contact' ? 'bg-white text-[#8C2B2B]' : 'bg-[#8C2B2B] text-white'}`}>{contactMessages.length}</span>
            )}
          </button>
        )}
        {isAdmin && (
          <button onClick={() => { setTab('history'); loadHistory(); }}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-bold transition-colors flex-1 justify-center min-w-0 ${tab === 'history' ? 'bg-[#8C2B2B] text-white' : 'text-[#8C7A6B] hover:bg-[#F0EBE1]'}`}>
            <History size={16} /> <span className="truncate">היסטוריה</span>
          </button>
        )}
        {isAdmin && (
          <button onClick={() => { setTab('recordings'); loadRecordings(); }}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-bold transition-colors flex-1 justify-center min-w-0 ${tab === 'recordings' ? 'bg-[#8C2B2B] text-white' : 'text-[#8C7A6B] hover:bg-[#F0EBE1]'}`}>
            <Headphones size={16} /> <span className="truncate">ניהול הקלטות</span>
          </button>
        )}
      </div>

      {/* Beit Midrash tab */}
      {tab === 'beit-midrash' && (
        <div className="bg-white p-4 sm:p-6 rounded-2xl shadow-sm border border-[#E5E0D8]">
          <h2 className="text-xl font-bold text-[#4A3B32] mb-2 flex items-center gap-2">
            <Bell size={24} className="text-[#8C2B2B]" /> תגובות ממתינות ({unansweredComments.length})
          </h2>
          <p className="text-sm text-[#8C7A6B] mb-4">לחץ על תגובה כדי לפתוח ולהגיב</p>
          {unansweredComments.length === 0 ? (
            <p className="text-[#8C7A6B] text-center py-8">אין תגובות ממתינות - מצוין!</p>
          ) : (
            <div className="space-y-2">
              {unansweredComments.map((comment, idx) => {
                const key = `${comment.sectionId}-${comment.id}`;
                const link = sectionLink(comment);
                const isOpen = expandedId === key;
                return (
                  <div key={idx} className="border border-[#E5E0D8] rounded-xl overflow-hidden">
                    <button onClick={() => toggleExpand(key)}
                      className={`w-full flex items-center gap-3 px-4 py-3 text-right transition-colors ${isOpen ? 'bg-[#F0EBE1]' : 'bg-[#FAF8F5] hover:bg-[#F0EBE1]'}`}>
                      <ChevronDown size={16} className={`text-[#8C7A6B] shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
                      <span className="font-bold text-[#4A3B32] text-sm shrink-0">{comment.author}</span>
                      <span className="text-xs text-[#8C7A6B] truncate flex-1">{comment.bookTitle} &gt; {comment.sectionTitle}</span>
                      <span className="text-xs text-[#8C7A6B] shrink-0">{comment.date}</span>
                    </button>
                    {isOpen && (
                      <div className="px-4 py-4 bg-[#FAF8F5] border-t border-[#E5E0D8]">
                        <p className="text-[#4A3B32] mb-3 bg-white p-3 rounded-lg border border-[#E5E0D8] text-sm">{comment.text}</p>
                        <div className="flex items-center gap-3 mb-3">
                          {link && (
                            <Link href={link} className="inline-flex items-center gap-1 text-xs text-[#8C2B2B] hover:underline">
                              <ExternalLink size={12} /> פתח באתר
                            </Link>
                          )}
                          <button onClick={() => handleResolveComment(comment.sectionId, comment.id)}
                            className="inline-flex items-center gap-1 text-xs font-bold text-green-700 bg-green-50 px-2.5 py-1 rounded-lg hover:bg-green-100 transition-colors mr-auto">
                            <CheckCircle size={14} /> סמן כטופל
                          </button>
                        </div>
                        <div className="pt-3 border-t border-[#E5E0D8]">
                          <textarea value={replyText[key] || ''} onChange={(e) => setReplyText({ ...replyText, [key]: e.target.value })}
                            className="w-full p-3 rounded-xl border border-[#E5E0D8] bg-white focus:ring-2 focus:ring-[#8C2B2B] outline-none resize-none mb-3 text-sm" rows={2} placeholder="הכנס תשובה כאן..." />
                          <div className="mb-3">
                            <AudioRecorder
                              sectionId={comment.sectionId}
                              commentId={comment.id}
                              authorName={user?.name || 'rabbi'}
                              audioUrl={replyAudio[key] || null}
                              onRecorded={(url) => setReplyAudio({ ...replyAudio, [key]: url })}
                              onClear={() => setReplyAudio({ ...replyAudio, [key]: '' })}
                            />
                          </div>
                          <div className="flex justify-end">
                            <button onClick={() => handleReplySubmit(comment.sectionId, comment.id)}
                              className="px-4 py-2 bg-[#8C2B2B] text-white rounded-lg hover:bg-[#7A2525] transition-colors text-sm font-bold">שלח תשובה</button>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Editor Questions tab */}
      {tab === 'editor' && (
        <div className="bg-white p-4 sm:p-6 rounded-2xl shadow-sm border border-[#E5E0D8]">
          <h2 className="text-xl font-bold text-[#4A3B32] mb-2 flex items-center gap-2">
            <MessageSquare size={24} className="text-[#8C2B2B]" /> שאלות מהעורכים ({questions.length})
          </h2>
          <p className="text-sm text-[#8C7A6B] mb-4">לחץ על שאלה כדי לראות פרטים ולהגיב</p>
          {questions.length === 0 ? (
            <p className="text-[#8C7A6B] text-center py-8">אין שאלות מהעורכים.</p>
          ) : (
            <div className="space-y-2">
              {questions.map((q, idx) => {
                const qKey = `editor-${q.sectionId}-${q.id}`;
                const replyKey = `editor-${q.sectionId}-${q.id}`;
                const link = sectionLink(q);
                const isOpen = expandedId === qKey;
                return (
                  <div key={idx} className="border border-[#E5E0D8] rounded-xl overflow-hidden">
                    <button onClick={() => toggleExpand(qKey)}
                      className={`w-full flex items-center gap-3 px-4 py-3 text-right transition-colors ${isOpen ? 'bg-[#F0EBE1]' : 'bg-[#FAF8F5] hover:bg-[#F0EBE1]'}`}>
                      <ChevronDown size={16} className={`text-[#8C7A6B] shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
                      <span className="font-bold text-[#4A3B32] text-sm shrink-0">{q.author}</span>
                      <span className="text-xs text-[#8C7A6B] truncate flex-1">{q.bookTitle} &gt; {q.sectionTitle}</span>
                      <span className="text-xs text-[#8C7A6B] shrink-0">{q.date}</span>
                    </button>
                    {isOpen && (
                      <div className="px-4 py-4 bg-[#FAF8F5] border-t border-[#E5E0D8]">
                        {q.selectedText && (
                          <div className="mb-3 p-3 bg-yellow-50 border-r-4 border-yellow-400 rounded-lg text-sm text-[#4A3B32]">
                            <span className="text-xs font-bold text-yellow-700 block mb-1">טקסט מסומן:</span>
                            &ldquo;{q.selectedText}&rdquo;
                          </div>
                        )}
                        <p className="text-[#4A3B32] mb-3 bg-white p-3 rounded-lg border border-[#E5E0D8] text-sm">{q.text}</p>
                        {q.replies && q.replies.length > 0 && (
                          <div className="mr-4 pr-4 border-r-2 border-[#E5E0D8] space-y-2 mb-3">
                            {q.replies.map((reply: any) => (
                              <div key={reply.id} className="bg-[#F0EBE1] p-3 rounded-lg text-sm">
                                <div className="flex justify-between mb-1">
                                  <span className="font-bold text-[#8C2B2B]">{reply.author}</span>
                                  <span className="text-xs text-[#8C7A6B]">{reply.date}</span>
                                </div>
                                {reply.text && <p className="text-[#4A3B32]">{reply.text}</p>}
                                {reply.audioUrl && <div className="mt-1"><AudioPlayer src={reply.audioUrl} /></div>}
                              </div>
                            ))}
                          </div>
                        )}
                        <div className="flex items-center gap-3 mb-3">
                          {link && (
                            <Link href={link} className="inline-flex items-center gap-1 text-xs text-[#8C2B2B] hover:underline">
                              <ExternalLink size={12} /> פתח באתר
                            </Link>
                          )}
                          <button onClick={() => handleResolveQuestion(q.sectionId, q.id)}
                            className="inline-flex items-center gap-1 text-xs font-bold text-green-700 bg-green-50 px-2.5 py-1 rounded-lg hover:bg-green-100 transition-colors mr-auto">
                            <CheckCircle size={14} /> סמן כטופל
                          </button>
                        </div>
                        <div className="pt-3 border-t border-[#E5E0D8]">
                          <textarea value={replyText[replyKey] || ''} onChange={(e) => setReplyText({ ...replyText, [replyKey]: e.target.value })}
                            className="w-full p-3 rounded-xl border border-[#E5E0D8] bg-white focus:ring-2 focus:ring-[#8C2B2B] outline-none resize-none mb-3 text-sm" rows={2} placeholder="הכנס תשובה כאן..." />
                          <div className="mb-3">
                            <AudioRecorder
                              sectionId={q.sectionId}
                              commentId={q.id}
                              authorName={user?.name || 'rabbi'}
                              audioUrl={replyAudio[replyKey] || null}
                              onRecorded={(url) => setReplyAudio({ ...replyAudio, [replyKey]: url })}
                              onClear={() => setReplyAudio({ ...replyAudio, [replyKey]: '' })}
                            />
                          </div>
                          <div className="flex justify-end">
                            <button onClick={() => handleEditorQuestionReply(q.sectionId, q.id)}
                              className="px-4 py-2 bg-[#8C2B2B] text-white rounded-lg hover:bg-[#7A2525] transition-colors text-sm font-bold">שלח תשובה</button>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Contact Messages tab */}
      {tab === 'contact' && (
        <div className="bg-white p-4 sm:p-6 rounded-2xl shadow-sm border border-[#E5E0D8]">
          <h2 className="text-xl font-bold text-[#4A3B32] mb-2 flex items-center gap-2">
            <Mail size={24} className="text-[#8C2B2B]" /> הודעות מטופס צור קשר ({contactMessages.length})
          </h2>
          <p className="text-sm text-[#8C7A6B] mb-4">לחץ על הודעה כדי לראות פרטים ולהגיב</p>
          {contactMessages.length === 0 ? (
            <p className="text-[#8C7A6B] text-center py-8">אין הודעות ממתינות.</p>
          ) : (
            <div className="space-y-2">
              {contactMessages.map((msg) => {
                const key = `contact-${msg.id}`;
                const isOpen = expandedId === key;
                return (
                  <div key={msg.id} className="border border-[#E5E0D8] rounded-xl overflow-hidden">
                    <button onClick={() => toggleExpand(key)}
                      className={`w-full flex items-center gap-3 px-4 py-3 text-right transition-colors ${isOpen ? 'bg-[#F0EBE1]' : 'bg-[#FAF8F5] hover:bg-[#F0EBE1]'}`}>
                      <ChevronDown size={16} className={`text-[#8C7A6B] shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
                      <span className="font-bold text-[#4A3B32] text-sm shrink-0">{msg.name}</span>
                      <span className="text-xs text-[#8C7A6B] truncate flex-1">{msg.subject || 'ללא נושא'}</span>
                      <span className="text-xs text-[#8C7A6B] shrink-0">{msg.date}</span>
                    </button>
                    {isOpen && (
                      <div className="px-4 py-4 bg-[#FAF8F5] border-t border-[#E5E0D8]">
                        {msg.email && (
                          <div className="mb-3 text-xs text-[#8C7A6B]">
                            אימייל: <a href={`mailto:${msg.email}`} className="text-[#8C2B2B] hover:underline">{msg.email}</a>
                          </div>
                        )}
                        <p className="text-[#4A3B32] mb-3 bg-white p-3 rounded-lg border border-[#E5E0D8] text-sm whitespace-pre-wrap">{msg.message}</p>
                        {msg.replies && msg.replies.length > 0 && (
                          <div className="mr-4 pr-4 border-r-2 border-[#E5E0D8] space-y-2 mb-3">
                            {msg.replies.map((reply: any) => (
                              <div key={reply.id} className="bg-[#F0EBE1] p-3 rounded-lg text-sm">
                                <div className="flex justify-between mb-1">
                                  <span className="font-bold text-[#8C2B2B]">{reply.author}</span>
                                  <span className="text-xs text-[#8C7A6B]">{reply.date}</span>
                                </div>
                                {reply.text && <p className="text-[#4A3B32]">{reply.text}</p>}
                                {reply.audioUrl && <div className="mt-1"><AudioPlayer src={reply.audioUrl} /></div>}
                              </div>
                            ))}
                          </div>
                        )}
                        <div className="flex items-center gap-3 mb-3">
                          <button onClick={() => handleResolveContact(msg.id)}
                            className="inline-flex items-center gap-1 text-xs font-bold text-green-700 bg-green-50 px-2.5 py-1 rounded-lg hover:bg-green-100 transition-colors mr-auto">
                            <CheckCircle size={14} /> סמן כטופל
                          </button>
                        </div>
                        <div className="pt-3 border-t border-[#E5E0D8]">
                          <textarea value={replyText[key] || ''} onChange={(e) => setReplyText({ ...replyText, [key]: e.target.value })}
                            className="w-full p-3 rounded-xl border border-[#E5E0D8] bg-white focus:ring-2 focus:ring-[#8C2B2B] outline-none resize-none mb-3 text-sm" rows={2} placeholder="הכנס תשובה כאן..." />
                          <div className="flex justify-end">
                            <button onClick={() => handleContactReply(msg.id)}
                              className="px-4 py-2 bg-[#8C2B2B] text-white rounded-lg hover:bg-[#7A2525] transition-colors text-sm font-bold">שלח תשובה</button>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Recordings Management tab - admin only */}
      {tab === 'recordings' && isAdmin && (
        <div className="bg-white p-4 sm:p-6 rounded-2xl shadow-sm border border-[#E5E0D8]">
          <h2 className="text-xl font-bold text-[#4A3B32] mb-2 flex items-center gap-2">
            <Headphones size={24} className="text-[#8C2B2B]" /> ניהול הקלטות ({recordings.length})
          </h2>
          <p className="text-sm text-[#8C7A6B] mb-4">כל ההקלטות שהועלו לפיירבייס סטורג&apos;</p>
          {recordingsLoading ? (
            <div className="flex justify-center py-12"><BookLoader /></div>
          ) : recordings.length === 0 ? (
            <p className="text-[#8C7A6B] text-center py-8">אין הקלטות.</p>
          ) : (
            <div className="space-y-2">
              {recordings.map((rec) => (
                <div key={rec.fullPath} className="border border-[#E5E0D8] rounded-xl p-4 bg-[#FAF8F5]">
                  <div className="flex items-start gap-3">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-bold text-[#4A3B32] truncate">{rec.name}</p>
                      <p className="text-xs text-[#8C7A6B] mt-1">{rec.details}</p>
                      <p className="text-xs text-[#8C7A6B]">
                        {new Date(rec.timeCreated).toLocaleDateString('he-IL')} &bull; {(rec.size / 1024).toFixed(0)} KB
                      </p>
                      <div className="mt-2">
                        <AudioPlayer src={rec.url} />
                      </div>
                    </div>
                    <div className="shrink-0">
                      {confirmDelete === rec.fullPath ? (
                        <div className="flex flex-col items-center gap-1.5 bg-red-50 p-2 rounded-lg border border-red-200">
                          <div className="flex items-center gap-1 text-xs text-red-700">
                            <AlertTriangle size={12} />
                            <span>מחיקה לצמיתות!</span>
                          </div>
                          <div className="flex gap-1.5">
                            <button
                              onClick={() => deleteRecording(rec.fullPath)}
                              disabled={deletingPath === rec.fullPath}
                              className="px-2.5 py-1 text-xs font-bold bg-red-600 text-white rounded hover:bg-red-700 transition-colors disabled:opacity-50">
                              {deletingPath === rec.fullPath ? <Loader2 size={12} className="animate-spin" /> : 'מחק'}
                            </button>
                            <button
                              onClick={() => setConfirmDelete(null)}
                              className="px-2.5 py-1 text-xs text-[#8C7A6B] border border-[#E5E0D8] rounded hover:bg-white transition-colors">
                              ביטול
                            </button>
                          </div>
                        </div>
                      ) : (
                        <button onClick={() => setConfirmDelete(rec.fullPath)}
                          className="p-2 text-red-500 hover:bg-red-50 rounded-lg transition-colors" title="מחק הקלטה">
                          <Trash2 size={18} />
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* History tab */}
      {tab === 'history' && (
        <div className="space-y-6">
          {historyLoading ? (
            <div className="flex justify-center py-12"><BookLoader /></div>
          ) : (
            <>
              {/* Resolved beit-midrash comments */}
              {historyComments.length > 0 && (
                <div className="bg-white p-4 sm:p-6 rounded-2xl shadow-sm border border-[#E5E0D8]">
                  <h2 className="text-lg font-bold text-[#4A3B32] mb-3 flex items-center gap-2">
                    <Bell size={20} className="text-[#8C7A6B]" /> בית מדרש ({historyComments.length})
                  </h2>
                  <div className="space-y-1.5">
                    {historyComments.map((comment, idx) => {
                      const key = `hist-comment-${comment.sectionId}-${comment.id}`;
                      const link = sectionLink(comment);
                      const isOpen = expandedId === key;
                      return (
                        <div key={idx} className="border border-[#E5E0D8] rounded-lg overflow-hidden">
                          <button onClick={() => toggleExpand(key)}
                            className={`w-full flex items-center gap-3 px-3 py-2 text-right transition-colors ${isOpen ? 'bg-[#F0EBE1]' : 'hover:bg-[#FAF8F5]'}`}>
                            <ChevronDown size={14} className={`text-[#8C7A6B] shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
                            <CheckCircle size={14} className="text-green-500 shrink-0" />
                            <span className="font-bold text-[#4A3B32] text-xs shrink-0">{comment.author}</span>
                            <span className="text-xs text-[#8C7A6B] truncate flex-1">{comment.bookTitle} &gt; {comment.sectionTitle}</span>
                            <span className="text-xs text-[#8C7A6B] shrink-0">{comment.date}</span>
                          </button>
                          {isOpen && (
                            <div className="px-4 py-3 bg-[#FAF8F5] border-t border-[#E5E0D8]">
                              <p className="text-[#4A3B32] mb-3 bg-white p-3 rounded-lg border border-[#E5E0D8] text-sm">{comment.text}</p>
                              {comment.replies && comment.replies.length > 0 && (
                                <div className="mr-4 pr-4 border-r-2 border-[#E5E0D8] space-y-2 mb-3">
                                  {comment.replies.map((reply: any) => (
                                    <div key={reply.id} className="bg-[#F0EBE1] p-3 rounded-lg text-sm">
                                      <div className="flex justify-between mb-1">
                                        <span className="font-bold text-[#8C2B2B]">{reply.author}</span>
                                        <span className="text-xs text-[#8C7A6B]">{reply.date}</span>
                                      </div>
                                      {reply.text && <p className="text-[#4A3B32]">{reply.text}</p>}
                                {reply.audioUrl && <div className="mt-1"><AudioPlayer src={reply.audioUrl} /></div>}
                                    </div>
                                  ))}
                                </div>
                              )}
                              {comment.resolvedBy && (
                                <p className="text-xs text-green-700">טופל ע&quot;י {comment.resolvedBy} &bull; {comment.resolvedDate}</p>
                              )}
                              {link && (
                                <Link href={link} className="inline-flex items-center gap-1 text-xs text-[#8C2B2B] hover:underline mt-2">
                                  <ExternalLink size={12} /> פתח באתר
                                </Link>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Resolved editor questions */}
              {historyQuestions.length > 0 && (
                <div className="bg-white p-4 sm:p-6 rounded-2xl shadow-sm border border-[#E5E0D8]">
                  <h2 className="text-lg font-bold text-[#4A3B32] mb-3 flex items-center gap-2">
                    <MessageSquare size={20} className="text-[#8C7A6B]" /> שאלות מהעורכים ({historyQuestions.length})
                  </h2>
                  <div className="space-y-1.5">
                    {historyQuestions.map((q, idx) => {
                      const key = `hist-q-${q.sectionId}-${q.id}`;
                      const link = sectionLink(q);
                      const isOpen = expandedId === key;
                      return (
                        <div key={idx} className="border border-[#E5E0D8] rounded-lg overflow-hidden">
                          <button onClick={() => toggleExpand(key)}
                            className={`w-full flex items-center gap-3 px-3 py-2 text-right transition-colors ${isOpen ? 'bg-[#F0EBE1]' : 'hover:bg-[#FAF8F5]'}`}>
                            <ChevronDown size={14} className={`text-[#8C7A6B] shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
                            <CheckCircle size={14} className="text-green-500 shrink-0" />
                            <span className="font-bold text-[#4A3B32] text-xs shrink-0">{q.author}</span>
                            <span className="text-xs text-[#8C7A6B] truncate flex-1">{q.bookTitle} &gt; {q.sectionTitle}</span>
                            <span className="text-xs text-[#8C7A6B] shrink-0">{q.date}</span>
                          </button>
                          {isOpen && (
                            <div className="px-4 py-3 bg-[#FAF8F5] border-t border-[#E5E0D8]">
                              {q.selectedText && (
                                <div className="mb-3 p-3 bg-yellow-50 border-r-4 border-yellow-400 rounded-lg text-sm text-[#4A3B32]">
                                  <span className="text-xs font-bold text-yellow-700 block mb-1">טקסט מסומן:</span>
                                  &ldquo;{q.selectedText}&rdquo;
                                </div>
                              )}
                              <p className="text-[#4A3B32] mb-3 bg-white p-3 rounded-lg border border-[#E5E0D8] text-sm">{q.text}</p>
                              {q.replies && q.replies.length > 0 && (
                                <div className="mr-4 pr-4 border-r-2 border-[#E5E0D8] space-y-2 mb-3">
                                  {q.replies.map((reply: any) => (
                                    <div key={reply.id} className="bg-[#F0EBE1] p-3 rounded-lg text-sm">
                                      <div className="flex justify-between mb-1">
                                        <span className="font-bold text-[#8C2B2B]">{reply.author}</span>
                                        <span className="text-xs text-[#8C7A6B]">{reply.date}</span>
                                      </div>
                                      {reply.text && <p className="text-[#4A3B32]">{reply.text}</p>}
                                {reply.audioUrl && <div className="mt-1"><AudioPlayer src={reply.audioUrl} /></div>}
                                    </div>
                                  ))}
                                </div>
                              )}
                              {q.resolvedBy && (
                                <p className="text-xs text-green-700">טופל ע&quot;י {q.resolvedBy} &bull; {q.resolvedDate}</p>
                              )}
                              {link && (
                                <Link href={link} className="inline-flex items-center gap-1 text-xs text-[#8C2B2B] hover:underline mt-2">
                                  <ExternalLink size={12} /> פתח באתר
                                </Link>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Resolved contact messages */}
              {historyContact.length > 0 && (
                <div className="bg-white p-4 sm:p-6 rounded-2xl shadow-sm border border-[#E5E0D8]">
                  <h2 className="text-lg font-bold text-[#4A3B32] mb-3 flex items-center gap-2">
                    <Mail size={20} className="text-[#8C7A6B]" /> צור קשר ({historyContact.length})
                  </h2>
                  <div className="space-y-1.5">
                    {historyContact.map((msg) => {
                      const key = `hist-contact-${msg.id}`;
                      const isOpen = expandedId === key;
                      return (
                        <div key={msg.id} className="border border-[#E5E0D8] rounded-lg overflow-hidden">
                          <button onClick={() => toggleExpand(key)}
                            className={`w-full flex items-center gap-3 px-3 py-2 text-right transition-colors ${isOpen ? 'bg-[#F0EBE1]' : 'hover:bg-[#FAF8F5]'}`}>
                            <ChevronDown size={14} className={`text-[#8C7A6B] shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
                            <CheckCircle size={14} className="text-green-500 shrink-0" />
                            <span className="font-bold text-[#4A3B32] text-xs shrink-0">{msg.name}</span>
                            <span className="text-xs text-[#8C7A6B] truncate flex-1">{msg.subject || 'ללא נושא'}</span>
                            <span className="text-xs text-[#8C7A6B] shrink-0">{msg.date}</span>
                          </button>
                          {isOpen && (
                            <div className="px-4 py-3 bg-[#FAF8F5] border-t border-[#E5E0D8]">
                              {msg.email && (
                                <div className="mb-3 text-xs text-[#8C7A6B]">
                                  אימייל: <a href={`mailto:${msg.email}`} className="text-[#8C2B2B] hover:underline">{msg.email}</a>
                                </div>
                              )}
                              <p className="text-[#4A3B32] mb-3 bg-white p-3 rounded-lg border border-[#E5E0D8] text-sm whitespace-pre-wrap">{msg.message}</p>
                              {msg.replies && msg.replies.length > 0 && (
                                <div className="mr-4 pr-4 border-r-2 border-[#E5E0D8] space-y-2 mb-3">
                                  {msg.replies.map((reply: any) => (
                                    <div key={reply.id} className="bg-[#F0EBE1] p-3 rounded-lg text-sm">
                                      <div className="flex justify-between mb-1">
                                        <span className="font-bold text-[#8C2B2B]">{reply.author}</span>
                                        <span className="text-xs text-[#8C7A6B]">{reply.date}</span>
                                      </div>
                                      {reply.text && <p className="text-[#4A3B32]">{reply.text}</p>}
                                {reply.audioUrl && <div className="mt-1"><AudioPlayer src={reply.audioUrl} /></div>}
                                    </div>
                                  ))}
                                </div>
                              )}
                              {msg.resolvedBy && (
                                <p className="text-xs text-green-700">טופל ע&quot;י {msg.resolvedBy} &bull; {msg.resolvedDate}</p>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Empty state */}
              {historyComments.length === 0 && historyQuestions.length === 0 && historyContact.length === 0 && (
                <div className="bg-white p-6 rounded-2xl shadow-sm border border-[#E5E0D8] text-center">
                  <p className="text-[#8C7A6B] py-8">אין היסטוריה עדיין.</p>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
