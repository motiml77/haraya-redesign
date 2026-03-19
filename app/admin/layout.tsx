'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { signInWithEmailAndPassword, signOut, onAuthStateChanged } from 'firebase/auth';
import { auth } from '@/lib/firebase';
import { authFetch } from '@/lib/auth-fetch';
import { LayoutDashboard, BookOpen, MessageSquare, LogOut, Loader2, Info, Hash, Bell, X } from 'lucide-react';
import { BookLoader } from '@/components/BookLoader';
import { SimpleMarkdown } from '@/components/MarkdownRenderer';
import { AdminContext, type AdminUser } from './admin-context';

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState<AdminUser | null>(null);
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [questionsBadge, setQuestionsBadge] = useState(0);
  const pathname = usePathname();

  // Announcements
  const [unreadAnnouncements, setUnreadAnnouncements] = useState<any[]>([]);
  const [showAnnouncementsPopup, setShowAnnouncementsPopup] = useState(false);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      if (firebaseUser) {
        try {
          const idToken = await firebaseUser.getIdToken();
          const res = await fetch('/api/auth', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ idToken }),
          });
          const data = await res.json();
          if (data.success) {
            setUser(data.user);
            setIsAuthenticated(true);
          } else {
            setIsAuthenticated(false);
            setUser(null);
          }
        } catch {
          setIsAuthenticated(false);
          setUser(null);
        }
      } else {
        setIsAuthenticated(false);
        setUser(null);
      }
      setIsLoading(false);
    });
    return () => unsubscribe();
  }, []);

  // Load questions badge + announcements in parallel when user is available
  useEffect(() => {
    if (!user) return;

    const fetches: Promise<void>[] = [];

    if (user.role === 'admin' || user.role === 'rabbi') {
      fetches.push(
        Promise.all([
          authFetch('/api/questions').then(res => res.json()).catch(() => ({ questions: [], unansweredComments: [] })),
          authFetch('/api/contact').then(res => res.json()).catch(() => []),
        ]).then(([questionsData, contactData]) => {
          const total = (questionsData.questions?.length || 0) +
            (questionsData.unansweredComments?.length || 0) +
            (Array.isArray(contactData) ? contactData.length : 0);
          setQuestionsBadge(total);
        })
      );
    }

    const typeParam = user.role === 'editor' ? '&type=editors' : '';
    fetches.push(
      authFetch(`/api/announcements?unreadFor=${user.id}${typeParam}`)
        .then(res => res.json())
        .then(data => {
          if (Array.isArray(data)) {
            setUnreadAnnouncements(data);
            if (data.length > 0) setShowAnnouncementsPopup(true);
          }
        })
        .catch(() => {})
    );

    Promise.all(fetches);
  }, [user]);

  const markAnnouncementRead = async (announcementId: string) => {
    try {
      await authFetch(`/api/announcements/${announcementId}`, {
        method: 'PUT',
        body: JSON.stringify({ action: 'markRead' }),
      });
      setUnreadAnnouncements(prev => prev.filter(a => a.id !== announcementId));
    } catch {}
  };

  const dismissAllAnnouncements = async () => {
    for (const a of unreadAnnouncements) {
      await authFetch(`/api/announcements/${a.id}`, {
        method: 'PUT',
        body: JSON.stringify({ action: 'markRead' }),
      });
    }
    setUnreadAnnouncements([]);
    setShowAnnouncementsPopup(false);
  };

  const handleLogin = async () => {
    if (isLoggingIn) return;
    setLoginError('');
    setIsLoggingIn(true);
    try {
      const credential = await signInWithEmailAndPassword(auth, loginEmail, loginPassword);
      const idToken = await credential.user.getIdToken();
      const res = await fetch('/api/auth', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idToken }),
      });
      const data = await res.json();
      if (data.success) {
        setUser(data.user);
        setIsAuthenticated(true);
      } else {
        setLoginError(data.error || 'שגיאה בהתחברות');
        await signOut(auth);
      }
    } catch (e: any) {
      if (e.code === 'auth/invalid-credential' || e.code === 'auth/wrong-password' || e.code === 'auth/user-not-found') {
        setLoginError('אימייל או סיסמה שגויים');
      } else {
        setLoginError('שגיאה בתקשורת');
      }
    }
    setIsLoggingIn(false);
  };

  const handleLogout = async () => {
    await signOut(auth);
    setIsAuthenticated(false);
    setUser(null);
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#FAF8F5] flex items-center justify-center" dir="rtl">
        <BookLoader />
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-[#FAF8F5] font-sans flex items-center justify-center p-6" dir="rtl">
        <div className="bg-white p-8 rounded-2xl shadow-sm border border-[#E5E0D8] w-full max-w-md">
          <h1 className="text-2xl font-serif font-bold text-[#4A3B32] mb-6 text-center">התחברות למערכת</h1>
          {loginError && <div className="bg-red-50 text-red-600 p-3 rounded-xl mb-4 text-sm font-bold">{loginError}</div>}
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-bold text-[#8C7A6B] mb-1">אימייל</label>
              <input type="email" value={loginEmail} onChange={(e) => setLoginEmail(e.target.value)}
                className="w-full p-3 rounded-xl border border-[#E5E0D8] bg-[#FAF8F5] focus:ring-2 focus:ring-[#8C2B2B] outline-none" placeholder="email@example.com" />
            </div>
            <div>
              <label className="block text-sm font-bold text-[#8C7A6B] mb-1">סיסמה</label>
              <input type="password" value={loginPassword} onChange={(e) => setLoginPassword(e.target.value)}
                className="w-full p-3 rounded-xl border border-[#E5E0D8] bg-[#FAF8F5] focus:ring-2 focus:ring-[#8C2B2B] outline-none" placeholder="••••••••"
                onKeyDown={(e) => e.key === 'Enter' && handleLogin()} />
            </div>
            <button onClick={handleLogin} disabled={isLoggingIn}
              className="w-full bg-[#8C2B2B] text-white py-3 rounded-xl hover:bg-[#7A2525] transition-colors font-bold mt-4 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed">
              {isLoggingIn && <Loader2 size={18} className="animate-spin" />}
              {isLoggingIn ? 'מתחבר...' : 'התחבר'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  const roleName = user?.role === 'admin' ? 'מנהל' : user?.role === 'rabbi' ? 'רב' : 'עורך';

  const navItems = [
    { href: '/admin', label: 'לוח בקרה', icon: LayoutDashboard, roles: ['admin', 'rabbi'] },
    { href: '/admin/books', label: 'ספרים ותוכן', icon: BookOpen, roles: ['admin', 'editor', 'rabbi'] },
    { href: '/admin/topics', label: 'נושאים', icon: Hash, roles: ['admin', 'editor', 'rabbi'] },
    { href: '/admin/questions', label: 'שאלות', icon: MessageSquare, roles: ['admin', 'rabbi'], badge: questionsBadge },
    { href: '/admin/about', label: 'אודות', icon: Info, roles: ['admin'] },
  ];

  return (
    <AdminContext.Provider value={{ user, questionsBadge, setQuestionsBadge }}>
      <div className="min-h-screen bg-[#FAF8F5] font-sans" dir="rtl">
        {/* Top bar */}
        <header className="bg-white border-b border-[#E5E0D8] px-3 sm:px-6 py-2 sm:py-3 sticky top-0 z-50 shadow-sm relative">
          <div className="max-w-7xl mx-auto flex justify-between items-center gap-2">
            {/* Left: logout + bell */}
            <div className="flex items-center gap-1 sm:gap-3 shrink-0">
              <button onClick={handleLogout} title="התנתק" className="flex items-center gap-1 text-xs sm:text-sm text-[#8C2B2B] hover:underline font-bold whitespace-nowrap">
                <LogOut size={16} />
                <span className="hidden sm:inline">התנתק</span>
              </button>
              <button onClick={() => setShowAnnouncementsPopup(!showAnnouncementsPopup)}
                className="relative p-1.5 sm:p-2 rounded-full hover:bg-[#F0EBE1] transition-colors">
                <Bell size={18} className="text-[#4A3B32]" />
                {unreadAnnouncements.length > 0 && (
                  <span className="absolute -top-1 -right-1 bg-[#8C2B2B] text-white text-[10px] font-bold w-4 h-4 sm:w-5 sm:h-5 rounded-full flex items-center justify-center">
                    {unreadAnnouncements.length > 9 ? '9+' : unreadAnnouncements.length}
                  </span>
                )}
              </button>
            </div>

            {/* Center: nav */}
            <nav className="flex bg-white rounded-full p-0.5 sm:p-1 shadow-sm border border-[#E5E0D8] overflow-x-auto">
              {navItems.filter(item => user && item.roles.includes(user.role)).map(item => (
                <Link key={item.href} href={item.href} title={item.label}
                  className={`relative flex items-center gap-1.5 px-2.5 sm:px-4 py-1.5 sm:py-2 rounded-full text-sm font-bold transition-colors whitespace-nowrap ${pathname === item.href ? 'bg-[#F0EBE1] text-[#4A3B32]' : 'text-[#8C7A6B] hover:text-[#4A3B32]'}`}>
                  <item.icon size={18} />
                  {'badge' in item && item.badge! > 0 && (
                    <span className="absolute -top-1 -right-1 bg-[#8C2B2B] text-white text-[10px] font-bold w-4 h-4 sm:w-5 sm:h-5 rounded-full flex items-center justify-center">
                      {item.badge! > 99 ? '99+' : item.badge}
                    </span>
                  )}
                  <span className="hidden lg:inline">{item.label}</span>
                </Link>
              ))}
            </nav>

            {/* Right: title + home */}
            <div className="flex items-center gap-2 sm:gap-4 shrink-0">
              <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-[#F0EBE1] rounded-full">
                <span className="text-xs font-bold text-[#8C7A6B]">{user?.name} ({roleName})</span>
              </div>
              <Link href="/" className="flex items-center gap-1 p-1.5 sm:p-2 rounded-full hover:bg-[#F0EBE1] transition-colors" title="חזרה לאתר">
                <BookOpen size={22} className="text-[#8C2B2B]" />
              </Link>
            </div>
          </div>

          {/* Announcements popup */}
          {showAnnouncementsPopup && (
            <div className="absolute left-6 top-16 w-96 max-h-[28rem] overflow-y-auto bg-white rounded-2xl shadow-xl border border-[#E5E0D8] z-[100] p-4">
              <div className="flex justify-between items-center mb-4">
                <h3 className="font-bold text-[#4A3B32] flex items-center gap-2"><Bell size={18} className="text-[#8C2B2B]" /> הודעות</h3>
                {unreadAnnouncements.length > 0 && (
                  <button onClick={dismissAllAnnouncements} className="text-xs text-[#8C2B2B] hover:underline font-bold">סמן הכל כנקרא</button>
                )}
              </div>
              {unreadAnnouncements.length === 0 ? (
                <p className="text-center text-sm text-[#8C7A6B] py-6">אין הודעות חדשות</p>
              ) : (
                <div className="space-y-3">
                  {unreadAnnouncements.map((a: any) => (
                    <div key={a.id} className="p-3 bg-[#FAF8F5] rounded-xl border border-[#E5E0D8]">
                      <div className="flex justify-between items-center mb-2">
                        <span className="font-bold text-sm text-[#4A3B32]">{a.title}</span>
                        <button onClick={() => markAnnouncementRead(a.id)} className="text-[#8C7A6B] hover:text-[#8C2B2B] p-0.5">
                          <X size={14} />
                        </button>
                      </div>
                      <div className="text-sm text-[#4A3B32] leading-relaxed">
                        <SimpleMarkdown>{a.content}</SimpleMarkdown>
                      </div>
                      <div className="flex items-center justify-between mt-2 pt-2 border-t border-[#E5E0D8]">
                        <span className="text-xs text-[#8C7A6B]">{a.createdBy}</span>
                        <span className="text-xs text-[#8C7A6B]">{new Date(a.createdAt).toLocaleDateString('he-IL')}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </header>

        {/* Content */}
        <main className="max-w-7xl mx-auto px-3 py-4 sm:p-6">
          {children}
        </main>
      </div>
    </AdminContext.Provider>
  );
}
