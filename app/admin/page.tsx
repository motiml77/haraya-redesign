'use client';

import React, { useState, useEffect } from 'react';
import { Users, Megaphone, Send, Loader2, Trash2, Key, Check, X } from 'lucide-react';
import { useAdminUser } from './admin-context';
import { BookLoader } from '@/components/BookLoader';
import { SimpleMarkdown } from '@/components/MarkdownRenderer';
import { authFetch } from '@/lib/auth-fetch';
import Link from 'next/link';

export default function AdminDashboard() {
  const { user } = useAdminUser();
  const [visitorsCount, setVisitorsCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);

  // Users management (admin only)
  const [users, setUsers] = useState<any[]>([]);
  const [isLoadingUsers, setIsLoadingUsers] = useState(false);

  // Announcements (admin/rabbi)
  const [announcementTitle, setAnnouncementTitle] = useState('');
  const [announcementContent, setAnnouncementContent] = useState('');
  const [announcementType, setAnnouncementType] = useState<'editors' | 'all'>('editors');
  const [isSendingAnnouncement, setIsSendingAnnouncement] = useState(false);
  const [recentAnnouncements, setRecentAnnouncements] = useState<any[]>([]);

  useEffect(() => {
    if (!user) return;
    const fetches: Promise<void>[] = [
      fetch('/api/analytics')
        .then(res => res.json())
        .then(data => setVisitorsCount(data.visitors || 0))
        .catch(console.error),
    ];
    if (user.role === 'admin') {
      setIsLoadingUsers(true);
      fetches.push(
        authFetch('/api/users').then(r => r.json()).then(data => {
          if (Array.isArray(data)) setUsers(data);
        }).catch(console.error)
        .finally(() => setIsLoadingUsers(false))
      );
    }
    if (user.role === 'admin' || user.role === 'rabbi') {
      fetches.push(
        authFetch('/api/announcements')
          .then(r => r.json())
          .then(data => { if (Array.isArray(data)) setRecentAnnouncements(data.slice(0, 5)); })
          .catch(() => {})
      );
    }
    Promise.all(fetches).finally(() => setIsLoading(false));
  }, [user]);

  const sendAnnouncement = async () => {
    if (!announcementTitle.trim() || !announcementContent.trim()) {
      alert('נא למלא כותרת ותוכן');
      return;
    }
    setIsSendingAnnouncement(true);
    try {
      const res = await authFetch('/api/announcements', {
        method: 'POST',
        body: JSON.stringify({ title: announcementTitle, content: announcementContent, type: announcementType }),
      });
      if (res.ok) {
        setAnnouncementTitle('');
        setAnnouncementContent('');
        alert('ההודעה נשלחה בהצלחה!');
        const data = await authFetch('/api/announcements').then(r => r.json());
        if (Array.isArray(data)) setRecentAnnouncements(data.slice(0, 5));
      } else {
        const data = await res.json();
        alert(data.error || 'שגיאה בשליחת הודעה');
      }
    } catch { alert('שגיאה בשליחת הודעה'); }
    setIsSendingAnnouncement(false);
  };

  const [editingRole, setEditingRole] = useState<string | null>(null);
  const [resetPasswordId, setResetPasswordId] = useState<string | null>(null);
  const [resetPasswordValue, setResetPasswordValue] = useState('');
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const handleChangeRole = async (userId: string, newRole: string) => {
    setActionLoading(userId);
    try {
      const res = await authFetch(`/api/users/${userId}`, { method: 'PUT', body: JSON.stringify({ role: newRole }) });
      if (res.ok) {
        setUsers(prev => prev.map(u => u.id === userId ? { ...u, role: newRole } : u));
        setEditingRole(null);
      } else {
        const data = await res.json();
        alert(data.error || 'שגיאה בעדכון תפקיד');
      }
    } catch { alert('שגיאה בעדכון תפקיד'); }
    setActionLoading(null);
  };

  const handleResetPassword = async (userId: string) => {
    if (!resetPasswordValue || resetPasswordValue.length < 6) {
      alert('סיסמה חייבת להיות לפחות 6 תווים');
      return;
    }
    setActionLoading(userId);
    try {
      const res = await authFetch(`/api/users/${userId}`, { method: 'PUT', body: JSON.stringify({ password: resetPasswordValue }) });
      if (res.ok) {
        setResetPasswordId(null);
        setResetPasswordValue('');
        alert('הסיסמה אופסה בהצלחה');
      } else {
        const data = await res.json();
        alert(data.error || 'שגיאה באיפוס סיסמה');
      }
    } catch { alert('שגיאה באיפוס סיסמה'); }
    setActionLoading(null);
  };

  const handleDeleteUser = async (userId: string, userName: string) => {
    if (!confirm(`האם למחוק את המשתמש "${userName}"? פעולה זו בלתי הפיכה.`)) return;
    setActionLoading(userId);
    try {
      const res = await authFetch(`/api/users/${userId}`, { method: 'DELETE' });
      if (res.ok) {
        setUsers(prev => prev.filter(u => u.id !== userId));
      } else {
        const data = await res.json();
        alert(data.error || 'שגיאה במחיקת משתמש');
      }
    } catch { alert('שגיאה במחיקת משתמש'); }
    setActionLoading(null);
  };

  const handleAddUser = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const data = {
      name: (form.elements.namedItem('name') as HTMLInputElement).value,
      email: (form.elements.namedItem('email') as HTMLInputElement).value,
      password: (form.elements.namedItem('password') as HTMLInputElement).value,
      role: (form.elements.namedItem('role') as HTMLSelectElement).value,
    };
    try {
      const res = await authFetch('/api/users', { method: 'POST', body: JSON.stringify(data) });
      if (res.ok) {
        form.reset();
        authFetch('/api/users').then(r => r.json()).then(d => { if (Array.isArray(d)) setUsers(d); });
        alert('משתמש נוסף בהצלחה!');
      } else {
        const errData = await res.json();
        alert(errData.error || 'שגיאה בהוספת משתמש');
      }
    } catch { alert('שגיאה בהוספת משתמש'); }
  };

  if (isLoading) return <BookLoader text="טוען לוח בקרה..." />;

  if (user?.role === 'editor') {
    return (
      <div className="text-center py-20 font-serif">
        <p className="text-[#6B5D4F] mb-4 italic">עורכים מנותבים לדף הספרים</p>
        <Link href="/admin/books" className="text-[#B14F1C] font-bold hover:underline tracking-wider">עבור לספרים ותוכן ←</Link>
      </div>
    );
  }

  const inputClass = "w-full p-2.5 border border-[#D6C8A8] bg-[#F1E6D2] focus:bg-white focus:border-[#B14F1C] focus:outline-none font-serif text-sm text-[#1F1A14]";
  const labelClass = "block text-xs font-bold text-[#1F1A14] mb-1.5 tracking-wider uppercase";
  const cardClass = "bg-[#E8DCC4] p-6 sm:p-8 border border-[#D6C8A8]";
  const sectionHeader = (label: string, title: string, Icon: any) => (
    <div className="mb-6 pb-4 border-b border-[#D6C8A8]">
      <div className="text-xs tracking-[0.25em] font-bold text-[#B14F1C] mb-2">● {label}</div>
      <h2 className="font-serif text-2xl text-[#1F1A14] flex items-center gap-2"><Icon size={20} className="text-[#B14F1C]" />{title}</h2>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className={`${cardClass} flex items-center gap-5 max-w-sm`}>
        <div className="bg-[#1F1A14] text-[#B14F1C] w-16 h-16 flex items-center justify-center"><Users size={28} /></div>
        <div>
          <p className="text-xs font-bold text-[#6B5D4F] tracking-wider uppercase mb-1">מבקרים ייחודיים</p>
          <p className="text-4xl font-serif font-semibold text-[#1F1A14]">{visitorsCount}</p>
        </div>
      </div>

      {/* Announcements - admin/rabbi */}
      {(user?.role === 'admin' || user?.role === 'rabbi') && (
        <div className={cardClass}>
          {sectionHeader('שליחת הודעה', 'הודעה למשתמשים', Megaphone)}
          <div className="space-y-4">
            <div>
              <label className={labelClass}>כותרת</label>
              <input type="text" value={announcementTitle} onChange={(e) => setAnnouncementTitle(e.target.value)}
                className={inputClass} placeholder="כותרת ההודעה..." />
            </div>
            <div>
              <label className={labelClass}>תוכן <span className="text-[10px] text-[#6B5D4F] font-normal normal-case">(תומך Markdown וקישורים)</span></label>
              <textarea value={announcementContent} onChange={(e) => setAnnouncementContent(e.target.value)}
                className={`${inputClass} resize-none leading-relaxed`} rows={4} placeholder="תוכן ההודעה..." />
            </div>
            {announcementContent.trim() && (
              <div className="p-4 bg-[#F1E6D2] border-r-4 border-[#B14F1C]">
                <span className="text-xs font-bold text-[#6B5D4F] tracking-wider uppercase block mb-2">תצוגה מקדימה</span>
                <div className="text-sm text-[#1F1A14] font-serif"><SimpleMarkdown>{announcementContent}</SimpleMarkdown></div>
              </div>
            )}
            <div className="flex items-center gap-4 flex-wrap">
              <label className={labelClass + " mb-0"}>יעד:</label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="radio" name="announcementType" value="editors" checked={announcementType === 'editors'} onChange={() => setAnnouncementType('editors')} className="accent-[#B14F1C]" />
                <span className="text-sm font-bold text-[#1F1A14] font-serif">עורכים בלבד</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="radio" name="announcementType" value="all" checked={announcementType === 'all'} onChange={() => setAnnouncementType('all')} className="accent-[#B14F1C]" />
                <span className="text-sm font-bold text-[#1F1A14] font-serif">כל המשתמשים</span>
              </label>
            </div>
            <button onClick={sendAnnouncement} disabled={isSendingAnnouncement}
              className="px-6 py-3 bg-[#1F1A14] text-[#F1E6D2] hover:bg-[#B14F1C] transition-colors font-bold flex items-center gap-2 disabled:opacity-50 tracking-wider text-sm">
              {isSendingAnnouncement ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
              {isSendingAnnouncement ? 'שולח...' : 'שלח הודעה'}
            </button>
          </div>

          {recentAnnouncements.length > 0 && (
            <div className="mt-6 pt-5 border-t border-[#D6C8A8]">
              <h3 className="text-xs font-bold text-[#6B5D4F] mb-3 tracking-wider uppercase">הודעות אחרונות</h3>
              <div className="space-y-2">
                {recentAnnouncements.map((a: any) => (
                  <div key={a.id} className="flex items-center justify-between p-3 bg-[#F1E6D2] border-r-2 border-[#D6C8A8] text-sm">
                    <div>
                      <span className="font-bold text-[#1F1A14] font-serif">{a.title}</span>
                      <span className="text-xs text-[#6B5D4F] mr-2">({a.type === 'editors' ? 'עורכים' : 'כולם'})</span>
                    </div>
                    <span className="text-xs text-[#6B5D4F]">{new Date(a.createdAt).toLocaleDateString('he-IL')}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Users Management - admin only */}
      {user?.role === 'admin' && (
        <>
          <div className={cardClass}>
            {sectionHeader('הוספת משתמש', 'משתמש חדש', Users)}
            <form onSubmit={handleAddUser} className="grid grid-cols-1 md:grid-cols-5 gap-4 items-end">
              <div>
                <label className={labelClass}>שם מלא</label>
                <input type="text" name="name" required className={inputClass} />
              </div>
              <div>
                <label className={labelClass}>אימייל</label>
                <input type="email" name="email" required className={inputClass} dir="ltr" />
              </div>
              <div>
                <label className={labelClass}>סיסמה</label>
                <input type="password" name="password" required minLength={6} className={inputClass} />
              </div>
              <div>
                <label className={labelClass}>תפקיד</label>
                <select name="role" required className={inputClass}>
                  <option value="editor">עורך</option>
                  <option value="rabbi">רב</option>
                  <option value="admin">מנהל</option>
                </select>
              </div>
              <button type="submit" className="w-full bg-[#1F1A14] text-[#F1E6D2] hover:bg-[#B14F1C] py-2.5 transition-colors font-bold tracking-wider text-sm">הוסף משתמש</button>
            </form>
          </div>

          <div className={cardClass}>
            {sectionHeader('רשימת משתמשים', 'כל המשתמשים', Users)}
            {isLoadingUsers ? (
              <div className="py-6 text-center text-[#6B5D4F] font-serif italic">טוען...</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-right">
                  <thead>
                    <tr className="border-b-2 border-[#D6C8A8] text-[#6B5D4F]">
                      <th className="py-3 px-4 font-bold text-xs tracking-wider uppercase">שם</th>
                      <th className="py-3 px-4 font-bold text-xs tracking-wider uppercase">אימייל</th>
                      <th className="py-3 px-4 font-bold text-xs tracking-wider uppercase">תפקיד</th>
                      <th className="py-3 px-4 font-bold text-xs tracking-wider uppercase">פעולות</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map(u => {
                      const isMe = u.id === user?.id;
                      const isLoadingRow = actionLoading === u.id;
                      return (
                        <tr key={u.id} className={`border-b border-[#D6C8A8] hover:bg-[#F1E6D2] ${isMe ? 'bg-[#F1E6D2]' : ''}`}>
                          <td className="py-3 px-4 font-bold text-[#1F1A14] font-serif">
                            {u.name}
                            {isMe && <span className="text-xs text-[#6B5D4F] mr-1 font-normal italic">(אתה)</span>}
                          </td>
                          <td className="py-3 px-4 text-[#6B5D4F] font-serif text-sm" dir="ltr">{u.email}</td>
                          <td className="py-3 px-4">
                            {editingRole === u.id ? (
                              <div className="flex items-center gap-1">
                                <select defaultValue={u.role} onChange={(e) => handleChangeRole(u.id, e.target.value)} disabled={isLoadingRow}
                                  className="p-1 border border-[#D6C8A8] bg-[#F1E6D2] text-xs font-bold outline-none">
                                  <option value="editor">עורך</option>
                                  <option value="rabbi">רב</option>
                                  <option value="admin">מנהל</option>
                                </select>
                                <button onClick={() => setEditingRole(null)} className="p-0.5 text-[#6B5D4F] hover:text-[#B14F1C]">
                                  <X size={14} />
                                </button>
                              </div>
                            ) : (
                              <button onClick={() => !isMe && setEditingRole(u.id)} disabled={isMe}
                                className={`px-2.5 py-1 text-xs font-bold tracking-wider uppercase border ${u.role === 'admin' ? 'border-[#B14F1C] text-[#B14F1C] bg-[#F1E6D2]' : u.role === 'rabbi' ? 'border-[#1F1A14] text-[#1F1A14] bg-[#F1E6D2]' : 'border-[#6B5D4F] text-[#6B5D4F] bg-[#F1E6D2]'} ${!isMe ? 'hover:bg-[#1F1A14] hover:text-[#F1E6D2] cursor-pointer transition-colors' : 'cursor-default'}`}
                                title={isMe ? '' : 'לחץ לשינוי תפקיד'}>
                                {u.role === 'admin' ? 'מנהל' : u.role === 'rabbi' ? 'רב' : 'עורך'}
                              </button>
                            )}
                          </td>
                          <td className="py-3 px-4">
                            {isLoadingRow ? (
                              <Loader2 size={16} className="animate-spin text-[#6B5D4F]" />
                            ) : (
                              <div className="flex items-center gap-1">
                                {resetPasswordId === u.id ? (
                                  <div className="flex items-center gap-1">
                                    <input type="password" value={resetPasswordValue} onChange={(e) => setResetPasswordValue(e.target.value)}
                                      placeholder="סיסמה חדשה" className="p-1 w-28 border border-[#D6C8A8] bg-[#F1E6D2] text-xs outline-none focus:border-[#B14F1C]" />
                                    <button onClick={() => handleResetPassword(u.id)} className="p-1 text-green-700 hover:bg-[#F1E6D2]" title="אשר">
                                      <Check size={14} />
                                    </button>
                                    <button onClick={() => { setResetPasswordId(null); setResetPasswordValue(''); }} className="p-1 text-[#6B5D4F] hover:text-[#B14F1C]" title="ביטול">
                                      <X size={14} />
                                    </button>
                                  </div>
                                ) : (
                                  <button onClick={() => setResetPasswordId(u.id)} className="p-1.5 text-[#6B5D4F] hover:text-[#B14F1C] hover:bg-[#F1E6D2] transition-colors" title="אפס סיסמה">
                                    <Key size={15} />
                                  </button>
                                )}
                                {!isMe && resetPasswordId !== u.id && (
                                  <button onClick={() => handleDeleteUser(u.id, u.name)} className="p-1.5 text-[#6B5D4F] hover:text-[#B14F1C] hover:bg-[#F1E6D2] transition-colors" title="מחק משתמש">
                                    <Trash2 size={15} />
                                  </button>
                                )}
                              </div>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
