'use client';

import React, { useState, useEffect } from 'react';
import { Users, Megaphone, Send, Loader2 } from 'lucide-react';
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

  // Load all dashboard data in parallel when user is available
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
      <div className="text-center py-20">
        <p className="text-[#8C7A6B] mb-4">עורכים מנותבים לדף הספרים</p>
        <Link href="/admin/books" className="text-[#8C2B2B] font-bold hover:underline">עבור לספרים ותוכן</Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="bg-white p-6 rounded-2xl shadow-sm border border-[#E5E0D8] flex items-center gap-4 max-w-sm">
        <div className="bg-[#F0EBE1] p-4 rounded-full text-[#8C2B2B]"><Users size={32} /></div>
        <div>
          <p className="text-sm font-bold text-[#8C7A6B]">מבקרים ייחודיים</p>
          <p className="text-3xl font-bold text-[#4A3B32]">{visitorsCount}</p>
        </div>
      </div>

      {/* Announcements - admin/rabbi */}
      {(user?.role === 'admin' || user?.role === 'rabbi') && (
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-[#E5E0D8]">
          <h2 className="text-xl font-bold text-[#4A3B32] mb-6 flex items-center gap-2">
            <Megaphone size={24} className="text-[#8C2B2B]" />
            שליחת הודעה
          </h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-bold text-[#8C7A6B] mb-1">כותרת</label>
              <input type="text" value={announcementTitle} onChange={(e) => setAnnouncementTitle(e.target.value)}
                className="w-full p-2.5 rounded-xl border border-[#E5E0D8] bg-[#FAF8F5] focus:ring-2 focus:ring-[#8C2B2B] outline-none" placeholder="כותרת ההודעה..." />
            </div>
            <div>
              <label className="block text-sm font-bold text-[#8C7A6B] mb-1">תוכן (תומך Markdown וקישורים)</label>
              <textarea value={announcementContent} onChange={(e) => setAnnouncementContent(e.target.value)}
                className="w-full p-3 rounded-xl border border-[#E5E0D8] bg-[#FAF8F5] focus:ring-2 focus:ring-[#8C2B2B] outline-none resize-none" rows={4} placeholder="תוכן ההודעה..." />
            </div>
            {/* Preview */}
            {announcementContent.trim() && (
              <div className="p-3 bg-[#FAF8F5] rounded-xl border border-[#E5E0D8]">
                <span className="text-xs font-bold text-[#8C7A6B] block mb-2">תצוגה מקדימה:</span>
                <div className="text-sm text-[#4A3B32]"><SimpleMarkdown>{announcementContent}</SimpleMarkdown></div>
              </div>
            )}
            <div className="flex items-center gap-4">
              <label className="block text-sm font-bold text-[#8C7A6B]">יעד:</label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="radio" name="announcementType" value="editors" checked={announcementType === 'editors'} onChange={() => setAnnouncementType('editors')} className="accent-[#8C2B2B]" />
                <span className="text-sm font-bold text-[#4A3B32]">עורכים בלבד</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="radio" name="announcementType" value="all" checked={announcementType === 'all'} onChange={() => setAnnouncementType('all')} className="accent-[#8C2B2B]" />
                <span className="text-sm font-bold text-[#4A3B32]">כל המשתמשים</span>
              </label>
            </div>
            <button onClick={sendAnnouncement} disabled={isSendingAnnouncement}
              className="px-6 py-2.5 bg-[#8C2B2B] text-white rounded-xl hover:bg-[#7A2525] transition-colors font-bold flex items-center gap-2 disabled:opacity-50">
              {isSendingAnnouncement ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
              {isSendingAnnouncement ? 'שולח...' : 'שלח הודעה'}
            </button>
          </div>

          {recentAnnouncements.length > 0 && (
            <div className="mt-6 pt-4 border-t border-[#E5E0D8]">
              <h3 className="text-sm font-bold text-[#8C7A6B] mb-3">הודעות אחרונות</h3>
              <div className="space-y-2">
                {recentAnnouncements.map((a: any) => (
                  <div key={a.id} className="flex items-center justify-between p-3 bg-[#FAF8F5] rounded-xl text-sm">
                    <div>
                      <span className="font-bold text-[#4A3B32]">{a.title}</span>
                      <span className="text-xs text-[#8C7A6B] mr-2">({a.type === 'editors' ? 'עורכים' : 'כולם'})</span>
                    </div>
                    <span className="text-xs text-[#8C7A6B]">{new Date(a.createdAt).toLocaleDateString('he-IL')}</span>
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
          <div className="bg-white p-6 rounded-2xl shadow-sm border border-[#E5E0D8]">
            <h2 className="text-xl font-bold text-[#4A3B32] mb-6 flex items-center gap-2">
              <Users size={24} className="text-[#8C2B2B]" />
              הוספת משתמש חדש
            </h2>
            <form onSubmit={handleAddUser} className="grid grid-cols-1 md:grid-cols-5 gap-4 items-end">
              <div>
                <label className="block text-sm font-bold text-[#8C7A6B] mb-1">שם מלא</label>
                <input type="text" name="name" required className="w-full p-2.5 rounded-xl border border-[#E5E0D8] bg-[#FAF8F5] focus:ring-2 focus:ring-[#8C2B2B] outline-none" />
              </div>
              <div>
                <label className="block text-sm font-bold text-[#8C7A6B] mb-1">אימייל</label>
                <input type="email" name="email" required className="w-full p-2.5 rounded-xl border border-[#E5E0D8] bg-[#FAF8F5] focus:ring-2 focus:ring-[#8C2B2B] outline-none" />
              </div>
              <div>
                <label className="block text-sm font-bold text-[#8C7A6B] mb-1">סיסמה</label>
                <input type="password" name="password" required minLength={6} className="w-full p-2.5 rounded-xl border border-[#E5E0D8] bg-[#FAF8F5] focus:ring-2 focus:ring-[#8C2B2B] outline-none" />
              </div>
              <div>
                <label className="block text-sm font-bold text-[#8C7A6B] mb-1">תפקיד</label>
                <select name="role" required className="w-full p-2.5 rounded-xl border border-[#E5E0D8] bg-[#FAF8F5] focus:ring-2 focus:ring-[#8C2B2B] outline-none">
                  <option value="editor">עורך</option>
                  <option value="rabbi">רב</option>
                  <option value="admin">מנהל</option>
                </select>
              </div>
              <button type="submit" className="w-full bg-[#4A3B32] text-white py-2.5 rounded-xl hover:bg-[#3A2B22] transition-colors font-bold">הוסף משתמש</button>
            </form>
          </div>

          <div className="bg-white p-6 rounded-2xl shadow-sm border border-[#E5E0D8]">
            <h2 className="text-xl font-bold text-[#4A3B32] mb-6 flex items-center gap-2">
              <Users size={24} className="text-[#8C2B2B]" />
              רשימת משתמשים
            </h2>
            {isLoadingUsers ? (
              <div className="py-6 text-center text-[#8C7A6B]">טוען...</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-right">
                  <thead>
                    <tr className="border-b border-[#E5E0D8] text-[#8C7A6B]">
                      <th className="py-3 px-4 font-bold">שם</th>
                      <th className="py-3 px-4 font-bold">אימייל</th>
                      <th className="py-3 px-4 font-bold">תפקיד</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map(u => (
                      <tr key={u.id} className="border-b border-[#F0EBE1] hover:bg-[#FAF8F5]">
                        <td className="py-3 px-4 font-bold text-[#4A3B32]">{u.name}</td>
                        <td className="py-3 px-4 text-[#8C7A6B]">{u.email}</td>
                        <td className="py-3 px-4">
                          <span className={`px-2 py-1 rounded-full text-xs font-bold ${u.role === 'admin' ? 'bg-red-100 text-red-800' : u.role === 'rabbi' ? 'bg-blue-100 text-blue-800' : 'bg-green-100 text-green-800'}`}>
                            {u.role === 'admin' ? 'מנהל' : u.role === 'rabbi' ? 'רב' : 'עורך'}
                          </span>
                        </td>
                      </tr>
                    ))}
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
