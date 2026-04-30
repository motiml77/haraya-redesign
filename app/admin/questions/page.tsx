'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { MessageSquare, Bell, ExternalLink, ChevronDown, CheckCircle, Mail, History, Headphones, Trash2, AlertTriangle, Loader2, FileText, Image as ImageIcon, File as FileIcon, Paperclip } from 'lucide-react';
import { BookLoader } from '@/components/BookLoader';
import { authFetch } from '@/lib/auth-fetch';
import { useAdminUser } from '../admin-context';
import { AudioRecorder } from '@/components/AudioRecorder';
import { AudioPlayer } from '@/components/AudioPlayer';
import { FileAttacher } from '@/components/FileAttacher';
import { storage, auth } from '@/lib/firebase';
import { ref, deleteObject } from 'firebase/storage';
import type { ReplyAttachment } from '@/lib/types';

export default function AdminQuestionsPage() {
 const { user, questionsBadge, setQuestionsBadge } = useAdminUser();
 const [questions, setQuestions] = useState<any[]>([]);
 const [unansweredComments, setUnansweredComments] = useState<any[]>([]);
 const [contactMessages, setContactMessages] = useState<any[]>([]);
 const [replyText, setReplyText] = useState<{ [key: string]: string }>({});
 const [replyAudio, setReplyAudio] = useState<{ [key: string]: string }>({});
 const [replyAttachments, setReplyAttachments] = useState<{ [key: string]: ReplyAttachment[] }>({});
 const [isLoading, setIsLoading] = useState(true);
 const [tab, setTab] = useState<'beit-midrash' | 'editor' | 'contact' | 'history' | 'recordings'>('beit-midrash');
 const [expandedId, setExpandedId] = useState<string | null>(null);

 // History state
 const [historyQuestions, setHistoryQuestions] = useState<any[]>([]);
 const [historyComments, setHistoryComments] = useState<any[]>([]);
 const [historyContact, setHistoryContact] = useState<any[]>([]);
 const [historyLoaded, setHistoryLoaded] = useState(false);
 const [historyLoading, setHistoryLoading] = useState(false);

 // Recording & files management state
 const [recordings, setRecordings] = useState<{ name: string; fullPath: string; url: string; size: number; timeCreated: string; sectionId: string; sectionTitle: string; bookTitle: string; authorName: string }[]>([]);
 const [uploadedFiles, setUploadedFiles] = useState<{ name: string; fullPath: string; url: string; size: number; timeCreated: string; sectionId: string; sectionTitle: string; bookTitle: string; authorName: string; fileType: 'pdf' | 'docx' | 'image' }[]>([]);
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
 const files = replyAttachments[key];
 if (!text && !audio && (!files || files.length === 0)) return;

 try {
 const sectionRes = await fetch(`/api/sections/${sectionId}`);
 const sectionData = await sectionRes.json();

 const reply: any = { id: Date.now(), author: user?.name || 'הרב המשיב', date: new Date().toISOString().split('T')[0], text: text || '' };
 if (audio) reply.audioUrl = audio;
 if (files && files.length > 0) reply.attachments = files;

 const updatedComments = (sectionData.comments || []).map((c: any) => {
 if (c.id === commentId) {
 return { ...c, replies: [...(c.replies || []), reply] };
 }
 return c;
 });

 await authFetch(`/api/sections/${sectionId}`, { method: 'PUT', body: JSON.stringify({ comments: updatedComments }) });
 setReplyText({ ...replyText, [key]: '' });
 setReplyAudio({ ...replyAudio, [key]: '' });
 setReplyAttachments({ ...replyAttachments, [key]: [] });
 setUnansweredComments(unansweredComments.filter(c => !(c.sectionId === sectionId && c.id === commentId)));
 setExpandedId(null);
 setHistoryLoaded(false);
 setQuestionsBadge((prev: number) => Math.max(0, prev - 1));
 } catch { alert('שגיאה בשליחת התשובה'); }
 };

 // Reply to editor question
 const handleEditorQuestionReply = async (sectionId: string, questionId: number | string) => {
 const key = `editor-${sectionId}-${questionId}`;
 const text = replyText[key];
 const audio = replyAudio[key];
 const files = replyAttachments[key];
 if (!text && !audio && (!files || files.length === 0)) return;

 try {
 const sectionRes = await fetch(`/api/sections/${sectionId}`);
 const sectionData = await sectionRes.json();

 const reply: any = { id: Date.now(), author: user?.name || 'הרב המשיב', date: new Date().toISOString().split('T')[0], text: text || '' };
 if (audio) reply.audioUrl = audio;
 if (files && files.length > 0) reply.attachments = files;

 const updatedQuestions = (sectionData.questionsForRabbi || []).map((q: any) => {
 if (q.id === questionId) {
 return { ...q, replies: [...(q.replies || []), reply] };
 }
 return q;
 });

 await authFetch(`/api/sections/${sectionId}`, { method: 'PUT', body: JSON.stringify({ questionsForRabbi: updatedQuestions }) });
 setReplyText({ ...replyText, [key]: '' });
 setReplyAudio({ ...replyAudio, [key]: '' });
 setReplyAttachments({ ...replyAttachments, [key]: [] });
 refreshData();
 setHistoryLoaded(false);
 setQuestionsBadge((prev: number) => Math.max(0, prev - 1));
 } catch { alert('שגיאה בשליחת התשובה'); }
 };

 // Reply to contact message
 const handleContactReply = async (messageId: string) => {
 const key = `contact-${messageId}`;
 const text = replyText[key];
 const audio = replyAudio[key];
 const files = replyAttachments[key];
 if (!text && !audio && (!files || files.length === 0)) return;

 try {
 const replyData: any = { author: user?.name || 'הרב המשיב', text: text || '' };
 if (audio) replyData.audioUrl = audio;
 if (files && files.length > 0) replyData.attachments = files;

 await authFetch(`/api/contact/${messageId}`, {
 method: 'PUT',
 body: JSON.stringify({ reply: replyData }),
 });
 setReplyText({ ...replyText, [key]: '' });
 setReplyAudio({ ...replyAudio, [key]: '' });
 setReplyAttachments({ ...replyAttachments, [key]: [] });
 refreshContact();
 setHistoryLoaded(false);
 setQuestionsBadge((prev: number) => Math.max(0, prev - 1));
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
 setQuestionsBadge((prev: number) => Math.max(0, prev - 1));
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
 setQuestionsBadge((prev: number) => Math.max(0, prev - 1));
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
 setQuestionsBadge((prev: number) => Math.max(0, prev - 1));
 } catch { alert('שגיאה בעדכון סטטוס'); }
 };

 // Load all recordings & uploaded files from Firebase Storage via REST API
 const loadRecordings = useCallback(async () => {
 if (recordingsLoaded) return;
 setRecordingsLoading(true);
 try {
 const bucket = storage.app.options.storageBucket;
 const token = await auth.currentUser?.getIdToken();
 if (!token) { setRecordingsLoading(false); return; }

 const sectionMap: Record<string, { sectionTitle: string; bookTitle: string }> = {};
 const sectionFetchPromises: Record<string, Promise<void>> = {};

 const fetchSectionTitle = (sectionId: string) => {
 if (sectionId && !sectionFetchPromises[sectionId]) {
 sectionFetchPromises[sectionId] = fetch(`/api/sections/${sectionId}`)
 .then(r => r.ok ? r.json() : null)
 .then(data => { if (data) sectionMap[sectionId] = { sectionTitle: data.title || sectionId, bookTitle: data.bookTitle || '' }; })
 .catch(() => {});
 }
 return sectionFetchPromises[sectionId];
 };

 // List audio-replies/ and reply-attachments/ in parallel
 const [audioListRes, filesListRes] = await Promise.all([
 fetch(`https://firebasestorage.googleapis.com/v0/b/${bucket}/o?prefix=audio-replies%2F&maxResults=500`, { headers: { 'Authorization': `Bearer ${token}` } }),
 fetch(`https://firebasestorage.googleapis.com/v0/b/${bucket}/o?prefix=reply-attachments%2F&maxResults=500`, { headers: { 'Authorization': `Bearer ${token}` } }),
 ]);

 const audioItems: any[] = audioListRes.ok ? ((await audioListRes.json()).items || []) : [];
 const fileItems: any[] = filesListRes.ok ? ((await filesListRes.json()).items || []) : [];

 // Process audio recordings
 const allAudio: typeof recordings = (await Promise.all(audioItems.map(async (item: any) => {
 try {
 const metaRes = await fetch(
 `https://firebasestorage.googleapis.com/v0/b/${bucket}/o/${encodeURIComponent(item.name)}`,
 { headers: { 'Authorization': `Bearer ${token}` } }
 );
 if (!metaRes.ok) return null;
 const meta = await metaRes.json();

 const pathParts = meta.name.split('/');
 const sectionId = pathParts.length >= 2 ? pathParts[1] : '';
 const fileName = pathParts[pathParts.length - 1] || '';
 const nameParts = fileName.replace(/\.[^.]+$/, '').split('_');
 const authorName = nameParts[2] || '?';

 await fetchSectionTitle(sectionId);
 const info = sectionMap[sectionId];
 const downloadToken = meta.downloadTokens || '';
 const url = `https://firebasestorage.googleapis.com/v0/b/${bucket}/o/${encodeURIComponent(meta.name)}?alt=media&token=${downloadToken}`;

 return {
 name: fileName, fullPath: meta.name, url,
 size: parseInt(meta.size || '0', 10), timeCreated: meta.timeCreated || '',
 sectionId, sectionTitle: info?.sectionTitle || sectionId, bookTitle: info?.bookTitle || '',
 authorName: decodeURIComponent(authorName).replace(/-/g, ' '),
 };
 } catch { return null; }
 }))).filter(Boolean) as typeof recordings;

 // Process uploaded files (PDF, Word, images)
 const allFiles: typeof uploadedFiles = (await Promise.all(fileItems.map(async (item: any) => {
 try {
 const metaRes = await fetch(
 `https://firebasestorage.googleapis.com/v0/b/${bucket}/o/${encodeURIComponent(item.name)}`,
 { headers: { 'Authorization': `Bearer ${token}` } }
 );
 if (!metaRes.ok) return null;
 const meta = await metaRes.json();

 const pathParts = meta.name.split('/');
 const sectionId = pathParts.length >= 2 ? pathParts[1] : '';
 const fileName = pathParts[pathParts.length - 1] || '';
 // Path format: reply-attachments/{sectionId}/reply_{commentId}_{authorName}_{timestamp}_{originalName}
 const nameParts = fileName.replace(/^reply_/, '').split('_');
 const authorName = nameParts.length >= 2 ? nameParts[1] : '?';

 await fetchSectionTitle(sectionId);
 const info = sectionMap[sectionId];
 const downloadToken = meta.downloadTokens || '';
 const url = `https://firebasestorage.googleapis.com/v0/b/${bucket}/o/${encodeURIComponent(meta.name)}?alt=media&token=${downloadToken}`;

 // Determine file type from content type
 const ct = meta.contentType || '';
 let fileType: 'pdf' | 'docx' | 'image' = 'image';
 if (ct === 'application/pdf') fileType = 'pdf';
 else if (ct.includes('wordprocessingml')) fileType = 'docx';

 return {
 name: fileName, fullPath: meta.name, url,
 size: parseInt(meta.size || '0', 10), timeCreated: meta.timeCreated || '',
 sectionId, sectionTitle: info?.sectionTitle || sectionId, bookTitle: info?.bookTitle || '',
 authorName: decodeURIComponent(authorName).replace(/-/g, ' '),
 fileType,
 };
 } catch { return null; }
 }))).filter(Boolean) as typeof uploadedFiles;

 allAudio.sort((a, b) => new Date(b.timeCreated).getTime() - new Date(a.timeCreated).getTime());
 allFiles.sort((a, b) => new Date(b.timeCreated).getTime() - new Date(a.timeCreated).getTime());
 setRecordings(allAudio);
 setUploadedFiles(allFiles);
 setRecordingsLoaded(true);
 } catch (err) {
 console.error('Error loading recordings/files:', err);
 }
 setRecordingsLoading(false);
 }, [recordingsLoaded]);

 const deleteStorageFile = useCallback(async (fullPath: string) => {
 setDeletingPath(fullPath);
 try {
 const fileRef = ref(storage, fullPath);
 await deleteObject(fileRef);
 setRecordings(prev => prev.filter(r => r.fullPath !== fullPath));
 setUploadedFiles(prev => prev.filter(f => f.fullPath !== fullPath));
 setConfirmDelete(null);
 } catch (err) {
 console.error('Delete error:', err);
 alert('שגיאה במחיקת הקובץ');
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
 <div className="grid grid-cols-2 sm:grid-cols-3 lg:flex gap-1.5 bg-[#E8DCC4] p-2 border border-[#D6C8A8]">
 <button onClick={() => setTab('beit-midrash')}
 className={`flex items-center justify-center gap-1.5 px-3 py-2.5 text-sm font-bold transition-colors ${tab === 'beit-midrash' ? 'bg-[#B14F1C] text-white' : 'text-[#6B5D4F] hover:bg-[#E8DCC4]'} lg:flex-1`}>
 <Bell size={16} /> <span>בית מדרש</span>
 {unansweredComments.length > 0 && (
 <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold ${tab === 'beit-midrash' ? 'bg-[#E8DCC4] text-[#B14F1C]' : 'bg-[#B14F1C] text-white'}`}>{unansweredComments.length}</span>
 )}
 </button>
 <button onClick={() => setTab('editor')}
 className={`flex items-center justify-center gap-1.5 px-3 py-2.5 text-sm font-bold transition-colors ${tab === 'editor' ? 'bg-[#B14F1C] text-white' : 'text-[#6B5D4F] hover:bg-[#E8DCC4]'} lg:flex-1`}>
 <MessageSquare size={16} /> <span>עורכים</span>
 {questions.length > 0 && (
 <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold ${tab === 'editor' ? 'bg-[#E8DCC4] text-[#B14F1C]' : 'bg-[#B14F1C] text-white'}`}>{questions.length}</span>
 )}
 </button>
 {isAdmin && (
 <button onClick={() => setTab('contact')}
 className={`flex items-center justify-center gap-1.5 px-3 py-2.5 text-sm font-bold transition-colors ${tab === 'contact' ? 'bg-[#B14F1C] text-white' : 'text-[#6B5D4F] hover:bg-[#E8DCC4]'} lg:flex-1`}>
 <Mail size={16} /> <span>צור קשר</span>
 {contactMessages.length > 0 && (
 <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold ${tab === 'contact' ? 'bg-[#E8DCC4] text-[#B14F1C]' : 'bg-[#B14F1C] text-white'}`}>{contactMessages.length}</span>
 )}
 </button>
 )}
 {isAdmin && (
 <button onClick={() => { setTab('history'); loadHistory(); }}
 className={`flex items-center justify-center gap-1.5 px-3 py-2.5 text-sm font-bold transition-colors ${tab === 'history' ? 'bg-[#B14F1C] text-white' : 'text-[#6B5D4F] hover:bg-[#E8DCC4]'} lg:flex-1`}>
 <History size={16} /> <span>היסטוריה</span>
 </button>
 )}
 {isAdmin && (
 <button onClick={() => { setTab('recordings'); loadRecordings(); }}
 className={`flex items-center justify-center gap-1.5 px-3 py-2.5 text-sm font-bold transition-colors ${tab === 'recordings' ? 'bg-[#B14F1C] text-white' : 'text-[#6B5D4F] hover:bg-[#E8DCC4]'} lg:flex-1`}>
 <Paperclip size={16} /> <span>הקלטות וקבצים</span>
 </button>
 )}
 </div>

 {/* Beit Midrash tab */}
 {tab === 'beit-midrash' && (
 <div className="bg-[#E8DCC4] p-4 sm:p-6 border border-[#D6C8A8]">
 <h2 className="text-xl font-bold text-[#1F1A14] mb-2 flex items-center gap-2">
 <Bell size={24} className="text-[#B14F1C]" /> תגובות ממתינות ({unansweredComments.length})
 </h2>
 <p className="text-sm text-[#6B5D4F] mb-4">לחץ על תגובה כדי לפתוח ולהגיב</p>
 {unansweredComments.length === 0 ? (
 <p className="text-[#6B5D4F] text-center py-8">אין תגובות ממתינות - מצוין!</p>
 ) : (
 <div className="space-y-2">
 {unansweredComments.map((comment, idx) => {
 const key = `${comment.sectionId}-${comment.id}`;
 const link = sectionLink(comment);
 const isOpen = expandedId === key;
 return (
 <div key={idx} className="border border-[#D6C8A8] overflow-hidden">
 <button onClick={() => toggleExpand(key)}
 className={`w-full flex items-center gap-3 px-4 py-3 text-right transition-colors ${isOpen ? 'bg-[#E8DCC4]' : 'bg-[#F1E6D2] hover:bg-[#E8DCC4]'}`}>
 <ChevronDown size={16} className={`text-[#6B5D4F] shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
 <span className="font-bold text-[#1F1A14] text-sm shrink-0">{comment.author}</span>
 <span className="text-xs text-[#6B5D4F] truncate flex-1">{comment.bookTitle} &gt; {comment.sectionTitle}</span>
 <span className="text-xs text-[#6B5D4F] shrink-0">{comment.date}</span>
 </button>
 {isOpen && (
 <div className="px-4 py-4 bg-[#F1E6D2] border-t border-[#D6C8A8]">
 <p className="text-[#1F1A14] mb-3 bg-[#E8DCC4] p-3 border border-[#D6C8A8] text-sm">{comment.text}</p>
 <div className="flex items-center gap-3 mb-3">
 {link && (
 <Link href={link} className="inline-flex items-center gap-1 text-xs text-[#B14F1C] hover:underline">
 <ExternalLink size={12} /> פתח באתר
 </Link>
 )}
 <button onClick={() => handleResolveComment(comment.sectionId, comment.id)}
 className="inline-flex items-center gap-1 text-xs font-bold text-green-700 bg-green-50 px-2.5 py-1 hover:bg-green-100 transition-colors mr-auto">
 <CheckCircle size={14} /> סמן כטופל
 </button>
 </div>
 <div className="pt-3 border-t border-[#D6C8A8]">
 <textarea value={replyText[key] || ''} onChange={(e) => setReplyText({ ...replyText, [key]: e.target.value })}
 className="w-full p-3 border border-[#D6C8A8] bg-[#E8DCC4] focus:border-[#B14F1C] outline-none resize-none mb-3 text-sm" rows={2} placeholder="הכנס תשובה כאן..." />
 <div className="mb-2">
 <AudioRecorder
 sectionId={comment.sectionId}
 commentId={comment.id}
 authorName={user?.name || 'rabbi'}
 audioUrl={replyAudio[key] || null}
 onRecorded={(url) => setReplyAudio({ ...replyAudio, [key]: url })}
 onClear={() => setReplyAudio({ ...replyAudio, [key]: '' })}
 />
 </div>
 <div className="mb-3">
 <FileAttacher
 sectionId={comment.sectionId}
 commentId={comment.id}
 authorName={user?.name || 'rabbi'}
 attachments={replyAttachments[key] || []}
 onAttachmentsChange={(atts) => setReplyAttachments({ ...replyAttachments, [key]: atts })}
 />
 </div>
 <div className="flex justify-end">
 <button onClick={() => handleReplySubmit(comment.sectionId, comment.id)}
 className="px-4 py-2 bg-[#B14F1C] text-white hover:bg-[#7A2525] transition-colors text-sm font-bold">שלח תשובה</button>
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
 <div className="bg-[#E8DCC4] p-4 sm:p-6 border border-[#D6C8A8]">
 <h2 className="text-xl font-bold text-[#1F1A14] mb-2 flex items-center gap-2">
 <MessageSquare size={24} className="text-[#B14F1C]" /> שאלות מהעורכים ({questions.length})
 </h2>
 <p className="text-sm text-[#6B5D4F] mb-4">לחץ על שאלה כדי לראות פרטים ולהגיב</p>
 {questions.length === 0 ? (
 <p className="text-[#6B5D4F] text-center py-8">אין שאלות מהעורכים.</p>
 ) : (
 <div className="space-y-2">
 {questions.map((q, idx) => {
 const qKey = `editor-${q.sectionId}-${q.id}`;
 const replyKey = `editor-${q.sectionId}-${q.id}`;
 const link = sectionLink(q);
 const isOpen = expandedId === qKey;
 return (
 <div key={idx} className="border border-[#D6C8A8] overflow-hidden">
 <button onClick={() => toggleExpand(qKey)}
 className={`w-full flex items-center gap-3 px-4 py-3 text-right transition-colors ${isOpen ? 'bg-[#E8DCC4]' : 'bg-[#F1E6D2] hover:bg-[#E8DCC4]'}`}>
 <ChevronDown size={16} className={`text-[#6B5D4F] shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
 <span className="font-bold text-[#1F1A14] text-sm shrink-0">{q.author}</span>
 <span className="text-xs text-[#6B5D4F] truncate flex-1">{q.bookTitle} &gt; {q.sectionTitle}</span>
 <span className="text-xs text-[#6B5D4F] shrink-0">{q.date}</span>
 </button>
 {isOpen && (
 <div className="px-4 py-4 bg-[#F1E6D2] border-t border-[#D6C8A8]">
 {q.selectedText && (
 <div className="mb-3 p-3 bg-yellow-50 border-r-4 border-yellow-400 text-sm text-[#1F1A14]">
 <span className="text-xs font-bold text-yellow-700 block mb-1">טקסט מסומן:</span>
 &ldquo;{q.selectedText}&rdquo;
 </div>
 )}
 <p className="text-[#1F1A14] mb-3 bg-[#E8DCC4] p-3 border border-[#D6C8A8] text-sm">{q.text}</p>
 {q.replies && q.replies.length > 0 && (
 <div className="mr-4 pr-4 border-r-2 border-[#D6C8A8] space-y-2 mb-3">
 {q.replies.map((reply: any) => (
 <div key={reply.id} className="bg-[#E8DCC4] p-3 text-sm">
 <div className="flex justify-between mb-1">
 <span className="font-bold text-[#B14F1C]">{reply.author}</span>
 <span className="text-xs text-[#6B5D4F]">{reply.date}</span>
 </div>
 {reply.text && <p className="text-[#1F1A14]">{reply.text}</p>}
 {reply.audioUrl && <div className="mt-1"><AudioPlayer src={reply.audioUrl} /></div>}
 {reply.attachments?.length > 0 && (
 <div className="mt-1 flex flex-wrap gap-1.5">
 {reply.attachments.map((att: any, ai: number) => (
 att.type === 'image' ? (
 <a key={ai} href={att.url} target="_blank" rel="noopener noreferrer">
 <img src={att.url} alt={att.name} className="max-w-[120px] max-h-[80px] border border-[#D6C8A8] object-cover" />
 </a>
 ) : (
 <a key={ai} href={att.url} target="_blank" rel="noopener noreferrer"
 className="flex items-center gap-1 px-2 py-1 bg-[#E8DCC4] border border-[#D6C8A8] text-[10px] text-[#1F1A14] hover:bg-[#F1E6D2]">
 {att.type === 'pdf' ? '📄' : '📝'} <span className="font-bold max-w-[100px] truncate">{att.name}</span>
 </a>
 )
 ))}
 </div>
 )}
 </div>
 ))}
 </div>
 )}
 <div className="flex items-center gap-3 mb-3">
 {link && (
 <Link href={link} className="inline-flex items-center gap-1 text-xs text-[#B14F1C] hover:underline">
 <ExternalLink size={12} /> פתח באתר
 </Link>
 )}
 <button onClick={() => handleResolveQuestion(q.sectionId, q.id)}
 className="inline-flex items-center gap-1 text-xs font-bold text-green-700 bg-green-50 px-2.5 py-1 hover:bg-green-100 transition-colors mr-auto">
 <CheckCircle size={14} /> סמן כטופל
 </button>
 </div>
 <div className="pt-3 border-t border-[#D6C8A8]">
 <textarea value={replyText[replyKey] || ''} onChange={(e) => setReplyText({ ...replyText, [replyKey]: e.target.value })}
 className="w-full p-3 border border-[#D6C8A8] bg-[#E8DCC4] focus:border-[#B14F1C] outline-none resize-none mb-3 text-sm" rows={2} placeholder="הכנס תשובה כאן..." />
 <div className="mb-2">
 <AudioRecorder
 sectionId={q.sectionId}
 commentId={q.id}
 authorName={user?.name || 'rabbi'}
 audioUrl={replyAudio[replyKey] || null}
 onRecorded={(url) => setReplyAudio({ ...replyAudio, [replyKey]: url })}
 onClear={() => setReplyAudio({ ...replyAudio, [replyKey]: '' })}
 />
 </div>
 <div className="mb-3">
 <FileAttacher
 sectionId={q.sectionId}
 commentId={q.id}
 authorName={user?.name || 'rabbi'}
 attachments={replyAttachments[replyKey] || []}
 onAttachmentsChange={(atts) => setReplyAttachments({ ...replyAttachments, [replyKey]: atts })}
 />
 </div>
 <div className="flex justify-end">
 <button onClick={() => handleEditorQuestionReply(q.sectionId, q.id)}
 className="px-4 py-2 bg-[#B14F1C] text-white hover:bg-[#7A2525] transition-colors text-sm font-bold">שלח תשובה</button>
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
 <div className="bg-[#E8DCC4] p-4 sm:p-6 border border-[#D6C8A8]">
 <h2 className="text-xl font-bold text-[#1F1A14] mb-2 flex items-center gap-2">
 <Mail size={24} className="text-[#B14F1C]" /> הודעות מטופס צור קשר ({contactMessages.length})
 </h2>
 <p className="text-sm text-[#6B5D4F] mb-4">לחץ על הודעה כדי לראות פרטים ולהגיב</p>
 {contactMessages.length === 0 ? (
 <p className="text-[#6B5D4F] text-center py-8">אין הודעות ממתינות.</p>
 ) : (
 <div className="space-y-2">
 {contactMessages.map((msg) => {
 const key = `contact-${msg.id}`;
 const isOpen = expandedId === key;
 return (
 <div key={msg.id} className="border border-[#D6C8A8] overflow-hidden">
 <button onClick={() => toggleExpand(key)}
 className={`w-full flex items-center gap-3 px-4 py-3 text-right transition-colors ${isOpen ? 'bg-[#E8DCC4]' : 'bg-[#F1E6D2] hover:bg-[#E8DCC4]'}`}>
 <ChevronDown size={16} className={`text-[#6B5D4F] shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
 <span className="font-bold text-[#1F1A14] text-sm shrink-0">{msg.name}</span>
 <span className="text-xs text-[#6B5D4F] truncate flex-1">{msg.subject || 'ללא נושא'}</span>
 <span className="text-xs text-[#6B5D4F] shrink-0">{msg.date}</span>
 </button>
 {isOpen && (
 <div className="px-4 py-4 bg-[#F1E6D2] border-t border-[#D6C8A8]">
 {msg.email && (
 <div className="mb-3 text-xs text-[#6B5D4F]">
 אימייל: <a href={`mailto:${msg.email}`} className="text-[#B14F1C] hover:underline">{msg.email}</a>
 </div>
 )}
 <p className="text-[#1F1A14] mb-3 bg-[#E8DCC4] p-3 border border-[#D6C8A8] text-sm whitespace-pre-wrap">{msg.message}</p>
 {msg.replies && msg.replies.length > 0 && (
 <div className="mr-4 pr-4 border-r-2 border-[#D6C8A8] space-y-2 mb-3">
 {msg.replies.map((reply: any) => (
 <div key={reply.id} className="bg-[#E8DCC4] p-3 text-sm">
 <div className="flex justify-between mb-1">
 <span className="font-bold text-[#B14F1C]">{reply.author}</span>
 <span className="text-xs text-[#6B5D4F]">{reply.date}</span>
 </div>
 {reply.text && <p className="text-[#1F1A14]">{reply.text}</p>}
 {reply.audioUrl && <div className="mt-1"><AudioPlayer src={reply.audioUrl} /></div>}
 {reply.attachments?.length > 0 && (
 <div className="mt-1 flex flex-wrap gap-1.5">
 {reply.attachments.map((att: any, ai: number) => (
 att.type === 'image' ? (
 <a key={ai} href={att.url} target="_blank" rel="noopener noreferrer">
 <img src={att.url} alt={att.name} className="max-w-[120px] max-h-[80px] border border-[#D6C8A8] object-cover" />
 </a>
 ) : (
 <a key={ai} href={att.url} target="_blank" rel="noopener noreferrer"
 className="flex items-center gap-1 px-2 py-1 bg-[#E8DCC4] border border-[#D6C8A8] text-[10px] text-[#1F1A14] hover:bg-[#F1E6D2]">
 {att.type === 'pdf' ? '📄' : '📝'} <span className="font-bold max-w-[100px] truncate">{att.name}</span>
 </a>
 )
 ))}
 </div>
 )}
 </div>
 ))}
 </div>
 )}
 <div className="flex items-center gap-3 mb-3">
 <button onClick={() => handleResolveContact(msg.id)}
 className="inline-flex items-center gap-1 text-xs font-bold text-green-700 bg-green-50 px-2.5 py-1 hover:bg-green-100 transition-colors mr-auto">
 <CheckCircle size={14} /> סמן כטופל
 </button>
 </div>
 <div className="pt-3 border-t border-[#D6C8A8]">
 <textarea value={replyText[key] || ''} onChange={(e) => setReplyText({ ...replyText, [key]: e.target.value })}
 className="w-full p-3 border border-[#D6C8A8] bg-[#E8DCC4] focus:border-[#B14F1C] outline-none resize-none mb-3 text-sm" rows={2} placeholder="הכנס תשובה כאן..." />
 <div className="mb-2">
 <AudioRecorder
 sectionId={msg.id}
 commentId={msg.id}
 authorName={user?.name || 'rabbi'}
 audioUrl={replyAudio[key] || null}
 onRecorded={(url) => setReplyAudio({ ...replyAudio, [key]: url })}
 onClear={() => setReplyAudio({ ...replyAudio, [key]: '' })}
 />
 </div>
 <div className="mb-3">
 <FileAttacher
 sectionId={msg.id}
 commentId={msg.id}
 authorName={user?.name || 'rabbi'}
 attachments={replyAttachments[key] || []}
 onAttachmentsChange={(atts) => setReplyAttachments({ ...replyAttachments, [key]: atts })}
 />
 </div>
 <div className="flex justify-end">
 <button onClick={() => handleContactReply(msg.id)}
 className="px-4 py-2 bg-[#B14F1C] text-white hover:bg-[#7A2525] transition-colors text-sm font-bold">שלח תשובה</button>
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

 {/* Recordings & Files Management tab - admin only */}
 {tab === 'recordings' && isAdmin && (
 <div className="space-y-4">
 {recordingsLoading ? (
 <div className="flex justify-center py-12"><BookLoader /></div>
 ) : (
 <>
 {/* Audio Recordings */}
 <div className="bg-[#E8DCC4] p-4 sm:p-6 border border-[#D6C8A8]">
 <h2 className="text-lg font-bold text-[#1F1A14] mb-2 flex items-center gap-2">
 <Headphones size={20} className="text-[#B14F1C]" /> הקלטות ({recordings.length})
 </h2>
 {recordings.length === 0 ? (
 <p className="text-[#6B5D4F] text-center py-4 text-sm">אין הקלטות.</p>
 ) : (
 <div className="space-y-1.5">
 {recordings.map((rec) => (
 <div key={rec.fullPath} className="border border-[#D6C8A8] px-3 py-2 bg-[#F1E6D2]">
 <div className="flex items-center gap-2">
 <div className="flex-1 min-w-0">
 <div className="flex items-center gap-2 flex-wrap">
 <p className="text-xs font-bold text-[#1F1A14] truncate">
 {rec.bookTitle && <span className="text-[#B14F1C]">{rec.bookTitle} &gt; </span>}
 {rec.sectionTitle}
 </p>
 <span className="text-[10px] text-[#6B5D4F]">
 {rec.authorName} &bull; {new Date(rec.timeCreated).toLocaleDateString('he-IL')}
 </span>
 </div>
 <div className="mt-1">
 <AudioPlayer src={rec.url} />
 </div>
 </div>
 <div className="shrink-0">
 {confirmDelete === rec.fullPath ? (
 <div className="flex items-center gap-1">
 <button onClick={() => deleteStorageFile(rec.fullPath)} disabled={deletingPath === rec.fullPath}
 className="px-2 py-0.5 text-[10px] font-bold bg-red-600 text-white hover:bg-red-700 transition-colors disabled:opacity-50">
 {deletingPath === rec.fullPath ? <Loader2 size={10} className="animate-spin" /> : 'מחק'}
 </button>
 <button onClick={() => setConfirmDelete(null)}
 className="px-2 py-0.5 text-[10px] text-[#6B5D4F] border border-[#D6C8A8] hover:bg-[#E8DCC4] transition-colors">ביטול</button>
 </div>
 ) : (
 <button onClick={() => setConfirmDelete(rec.fullPath)}
 className="p-1 text-red-400 hover:text-red-600 hover:bg-red-50 transition-colors" title="מחק הקלטה">
 <Trash2 size={14} />
 </button>
 )}
 </div>
 </div>
 </div>
 ))}
 </div>
 )}
 </div>

 {/* Uploaded Files (PDF, Word, Images) */}
 <div className="bg-[#E8DCC4] p-4 sm:p-6 border border-[#D6C8A8]">
 <h2 className="text-lg font-bold text-[#1F1A14] mb-2 flex items-center gap-2">
 <Paperclip size={20} className="text-[#B14F1C]" /> קבצים ותמונות ({uploadedFiles.length})
 </h2>
 {uploadedFiles.length === 0 ? (
 <p className="text-[#6B5D4F] text-center py-4 text-sm">אין קבצים מצורפים.</p>
 ) : (
 <div className="space-y-1.5">
 {uploadedFiles.map((file) => (
 <div key={file.fullPath} className="border border-[#D6C8A8] px-3 py-2 bg-[#F1E6D2]">
 <div className="flex items-center gap-2">
 {/* File type icon */}
 <div className="shrink-0">
 {file.fileType === 'pdf' ? <FileText size={18} className="text-red-500" /> :
 file.fileType === 'docx' ? <FileIcon size={18} className="text-blue-500" /> :
 <ImageIcon size={18} className="text-green-500" />}
 </div>
 <div className="flex-1 min-w-0">
 <div className="flex items-center gap-2 flex-wrap">
 <p className="text-xs font-bold text-[#1F1A14] truncate">
 {file.bookTitle && <span className="text-[#B14F1C]">{file.bookTitle} &gt; </span>}
 {file.sectionTitle}
 </p>
 <span className="text-[10px] text-[#6B5D4F]">
 {file.authorName} &bull; {new Date(file.timeCreated).toLocaleDateString('he-IL')} &bull; {file.size < 1024 * 1024 ? `${(file.size / 1024).toFixed(0)} KB` : `${(file.size / (1024 * 1024)).toFixed(1)} MB`}
 </span>
 </div>
 <div className="mt-0.5 flex items-center gap-2">
 {file.fileType === 'image' ? (
 <a href={file.url} target="_blank" rel="noopener noreferrer" className="text-[10px] text-[#B14F1C] hover:underline flex items-center gap-1">
 <ImageIcon size={10} /> צפה בתמונה
 </a>
 ) : (
 <a href={file.url} target="_blank" rel="noopener noreferrer" className="text-[10px] text-[#B14F1C] hover:underline flex items-center gap-1">
 <ExternalLink size={10} /> {file.fileType === 'pdf' ? 'פתח PDF' : 'הורד Word'}
 </a>
 )}
 <span className="text-[10px] text-[#6B5D4F] truncate max-w-[200px]">{file.name}</span>
 </div>
 </div>
 <div className="shrink-0">
 {confirmDelete === file.fullPath ? (
 <div className="flex items-center gap-1">
 <button onClick={() => deleteStorageFile(file.fullPath)} disabled={deletingPath === file.fullPath}
 className="px-2 py-0.5 text-[10px] font-bold bg-red-600 text-white hover:bg-red-700 transition-colors disabled:opacity-50">
 {deletingPath === file.fullPath ? <Loader2 size={10} className="animate-spin" /> : 'מחק'}
 </button>
 <button onClick={() => setConfirmDelete(null)}
 className="px-2 py-0.5 text-[10px] text-[#6B5D4F] border border-[#D6C8A8] hover:bg-[#E8DCC4] transition-colors">ביטול</button>
 </div>
 ) : (
 <button onClick={() => setConfirmDelete(file.fullPath)}
 className="p-1 text-red-400 hover:text-red-600 hover:bg-red-50 transition-colors" title="מחק קובץ">
 <Trash2 size={14} />
 </button>
 )}
 </div>
 </div>
 </div>
 ))}
 </div>
 )}
 </div>
 </>
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
 <div className="bg-[#E8DCC4] p-4 sm:p-6 border border-[#D6C8A8]">
 <h2 className="text-lg font-bold text-[#1F1A14] mb-3 flex items-center gap-2">
 <Bell size={20} className="text-[#6B5D4F]" /> בית מדרש ({historyComments.length})
 </h2>
 <div className="space-y-1.5">
 {historyComments.map((comment, idx) => {
 const key = `hist-comment-${comment.sectionId}-${comment.id}`;
 const link = sectionLink(comment);
 const isOpen = expandedId === key;
 return (
 <div key={idx} className="border border-[#D6C8A8] overflow-hidden">
 <button onClick={() => toggleExpand(key)}
 className={`w-full flex items-center gap-3 px-3 py-2 text-right transition-colors ${isOpen ? 'bg-[#E8DCC4]' : 'hover:bg-[#F1E6D2]'}`}>
 <ChevronDown size={14} className={`text-[#6B5D4F] shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
 <CheckCircle size={14} className="text-green-500 shrink-0" />
 <span className="font-bold text-[#1F1A14] text-xs shrink-0">{comment.author}</span>
 <span className="text-xs text-[#6B5D4F] truncate flex-1">{comment.bookTitle} &gt; {comment.sectionTitle}</span>
 <span className="text-xs text-[#6B5D4F] shrink-0">{comment.date}</span>
 </button>
 {isOpen && (
 <div className="px-4 py-3 bg-[#F1E6D2] border-t border-[#D6C8A8]">
 <p className="text-[#1F1A14] mb-3 bg-[#E8DCC4] p-3 border border-[#D6C8A8] text-sm">{comment.text}</p>
 {comment.replies && comment.replies.length > 0 && (
 <div className="mr-4 pr-4 border-r-2 border-[#D6C8A8] space-y-2 mb-3">
 {comment.replies.map((reply: any) => (
 <div key={reply.id} className="bg-[#E8DCC4] p-3 text-sm">
 <div className="flex justify-between mb-1">
 <span className="font-bold text-[#B14F1C]">{reply.author}</span>
 <span className="text-xs text-[#6B5D4F]">{reply.date}</span>
 </div>
 {reply.text && <p className="text-[#1F1A14]">{reply.text}</p>}
 {reply.audioUrl && <div className="mt-1"><AudioPlayer src={reply.audioUrl} /></div>}
 {reply.attachments?.length > 0 && (
 <div className="mt-1 flex flex-wrap gap-1.5">
 {reply.attachments.map((att: any, ai: number) => (
 att.type === 'image' ? (
 <a key={ai} href={att.url} target="_blank" rel="noopener noreferrer">
 <img src={att.url} alt={att.name} className="max-w-[120px] max-h-[80px] border border-[#D6C8A8] object-cover" />
 </a>
 ) : (
 <a key={ai} href={att.url} target="_blank" rel="noopener noreferrer"
 className="flex items-center gap-1 px-2 py-1 bg-[#E8DCC4] border border-[#D6C8A8] text-[10px] text-[#1F1A14] hover:bg-[#F1E6D2]">
 {att.type === 'pdf' ? '📄' : '📝'} <span className="font-bold max-w-[100px] truncate">{att.name}</span>
 </a>
 )
 ))}
 </div>
 )}
 </div>
 ))}
 </div>
 )}
 {comment.resolvedBy && (
 <p className="text-xs text-green-700">טופל ע&quot;י {comment.resolvedBy} &bull; {comment.resolvedDate}</p>
 )}
 {link && (
 <Link href={link} className="inline-flex items-center gap-1 text-xs text-[#B14F1C] hover:underline mt-2">
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
 <div className="bg-[#E8DCC4] p-4 sm:p-6 border border-[#D6C8A8]">
 <h2 className="text-lg font-bold text-[#1F1A14] mb-3 flex items-center gap-2">
 <MessageSquare size={20} className="text-[#6B5D4F]" /> שאלות מהעורכים ({historyQuestions.length})
 </h2>
 <div className="space-y-1.5">
 {historyQuestions.map((q, idx) => {
 const key = `hist-q-${q.sectionId}-${q.id}`;
 const link = sectionLink(q);
 const isOpen = expandedId === key;
 return (
 <div key={idx} className="border border-[#D6C8A8] overflow-hidden">
 <button onClick={() => toggleExpand(key)}
 className={`w-full flex items-center gap-3 px-3 py-2 text-right transition-colors ${isOpen ? 'bg-[#E8DCC4]' : 'hover:bg-[#F1E6D2]'}`}>
 <ChevronDown size={14} className={`text-[#6B5D4F] shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
 <CheckCircle size={14} className="text-green-500 shrink-0" />
 <span className="font-bold text-[#1F1A14] text-xs shrink-0">{q.author}</span>
 <span className="text-xs text-[#6B5D4F] truncate flex-1">{q.bookTitle} &gt; {q.sectionTitle}</span>
 <span className="text-xs text-[#6B5D4F] shrink-0">{q.date}</span>
 </button>
 {isOpen && (
 <div className="px-4 py-3 bg-[#F1E6D2] border-t border-[#D6C8A8]">
 {q.selectedText && (
 <div className="mb-3 p-3 bg-yellow-50 border-r-4 border-yellow-400 text-sm text-[#1F1A14]">
 <span className="text-xs font-bold text-yellow-700 block mb-1">טקסט מסומן:</span>
 &ldquo;{q.selectedText}&rdquo;
 </div>
 )}
 <p className="text-[#1F1A14] mb-3 bg-[#E8DCC4] p-3 border border-[#D6C8A8] text-sm">{q.text}</p>
 {q.replies && q.replies.length > 0 && (
 <div className="mr-4 pr-4 border-r-2 border-[#D6C8A8] space-y-2 mb-3">
 {q.replies.map((reply: any) => (
 <div key={reply.id} className="bg-[#E8DCC4] p-3 text-sm">
 <div className="flex justify-between mb-1">
 <span className="font-bold text-[#B14F1C]">{reply.author}</span>
 <span className="text-xs text-[#6B5D4F]">{reply.date}</span>
 </div>
 {reply.text && <p className="text-[#1F1A14]">{reply.text}</p>}
 {reply.audioUrl && <div className="mt-1"><AudioPlayer src={reply.audioUrl} /></div>}
 {reply.attachments?.length > 0 && (
 <div className="mt-1 flex flex-wrap gap-1.5">
 {reply.attachments.map((att: any, ai: number) => (
 att.type === 'image' ? (
 <a key={ai} href={att.url} target="_blank" rel="noopener noreferrer">
 <img src={att.url} alt={att.name} className="max-w-[120px] max-h-[80px] border border-[#D6C8A8] object-cover" />
 </a>
 ) : (
 <a key={ai} href={att.url} target="_blank" rel="noopener noreferrer"
 className="flex items-center gap-1 px-2 py-1 bg-[#E8DCC4] border border-[#D6C8A8] text-[10px] text-[#1F1A14] hover:bg-[#F1E6D2]">
 {att.type === 'pdf' ? '📄' : '📝'} <span className="font-bold max-w-[100px] truncate">{att.name}</span>
 </a>
 )
 ))}
 </div>
 )}
 </div>
 ))}
 </div>
 )}
 {q.resolvedBy && (
 <p className="text-xs text-green-700">טופל ע&quot;י {q.resolvedBy} &bull; {q.resolvedDate}</p>
 )}
 {link && (
 <Link href={link} className="inline-flex items-center gap-1 text-xs text-[#B14F1C] hover:underline mt-2">
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
 <div className="bg-[#E8DCC4] p-4 sm:p-6 border border-[#D6C8A8]">
 <h2 className="text-lg font-bold text-[#1F1A14] mb-3 flex items-center gap-2">
 <Mail size={20} className="text-[#6B5D4F]" /> צור קשר ({historyContact.length})
 </h2>
 <div className="space-y-1.5">
 {historyContact.map((msg) => {
 const key = `hist-contact-${msg.id}`;
 const isOpen = expandedId === key;
 return (
 <div key={msg.id} className="border border-[#D6C8A8] overflow-hidden">
 <button onClick={() => toggleExpand(key)}
 className={`w-full flex items-center gap-3 px-3 py-2 text-right transition-colors ${isOpen ? 'bg-[#E8DCC4]' : 'hover:bg-[#F1E6D2]'}`}>
 <ChevronDown size={14} className={`text-[#6B5D4F] shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
 <CheckCircle size={14} className="text-green-500 shrink-0" />
 <span className="font-bold text-[#1F1A14] text-xs shrink-0">{msg.name}</span>
 <span className="text-xs text-[#6B5D4F] truncate flex-1">{msg.subject || 'ללא נושא'}</span>
 <span className="text-xs text-[#6B5D4F] shrink-0">{msg.date}</span>
 </button>
 {isOpen && (
 <div className="px-4 py-3 bg-[#F1E6D2] border-t border-[#D6C8A8]">
 {msg.email && (
 <div className="mb-3 text-xs text-[#6B5D4F]">
 אימייל: <a href={`mailto:${msg.email}`} className="text-[#B14F1C] hover:underline">{msg.email}</a>
 </div>
 )}
 <p className="text-[#1F1A14] mb-3 bg-[#E8DCC4] p-3 border border-[#D6C8A8] text-sm whitespace-pre-wrap">{msg.message}</p>
 {msg.replies && msg.replies.length > 0 && (
 <div className="mr-4 pr-4 border-r-2 border-[#D6C8A8] space-y-2 mb-3">
 {msg.replies.map((reply: any) => (
 <div key={reply.id} className="bg-[#E8DCC4] p-3 text-sm">
 <div className="flex justify-between mb-1">
 <span className="font-bold text-[#B14F1C]">{reply.author}</span>
 <span className="text-xs text-[#6B5D4F]">{reply.date}</span>
 </div>
 {reply.text && <p className="text-[#1F1A14]">{reply.text}</p>}
 {reply.audioUrl && <div className="mt-1"><AudioPlayer src={reply.audioUrl} /></div>}
 {reply.attachments?.length > 0 && (
 <div className="mt-1 flex flex-wrap gap-1.5">
 {reply.attachments.map((att: any, ai: number) => (
 att.type === 'image' ? (
 <a key={ai} href={att.url} target="_blank" rel="noopener noreferrer">
 <img src={att.url} alt={att.name} className="max-w-[120px] max-h-[80px] border border-[#D6C8A8] object-cover" />
 </a>
 ) : (
 <a key={ai} href={att.url} target="_blank" rel="noopener noreferrer"
 className="flex items-center gap-1 px-2 py-1 bg-[#E8DCC4] border border-[#D6C8A8] text-[10px] text-[#1F1A14] hover:bg-[#F1E6D2]">
 {att.type === 'pdf' ? '📄' : '📝'} <span className="font-bold max-w-[100px] truncate">{att.name}</span>
 </a>
 )
 ))}
 </div>
 )}
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
 <div className="bg-[#E8DCC4] p-6 border border-[#D6C8A8] text-center">
 <p className="text-[#6B5D4F] py-8">אין היסטוריה עדיין.</p>
 </div>
 )}
 </>
 )}
 </div>
 )}
 </div>
 );
}
