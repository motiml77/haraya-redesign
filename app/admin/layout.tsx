'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { signInWithEmailAndPassword, signOut, onAuthStateChanged, setPersistence, browserLocalPersistence, browserSessionPersistence } from 'firebase/auth';
import { auth } from '@/lib/firebase';
import { authFetch } from '@/lib/auth-fetch';
import { LayoutDashboard, BookOpen, MessageSquare, LogOut, Loader2, Info, Hash, Bell, X, Key } from 'lucide-react';
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
  const [rememberMe, setRememberMe] = useState(true);
  const [questionsBadge, setQuestionsBadge] = useState(0);
  const pathname = usePathname();

  // Announcements
  const [unreadAnnouncements, setUnreadAnnouncements] = useState<any[]>([]);
  const [showAnnouncementsPopup, setShowAnnouncementsPopup] = useState(false);

  // Password change
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [passwordSuccess, setPasswordSuccess] = useState(false);
  const [isChangingPassword, setIsChangingPassword] = useState(false);

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
      await setPersistence(auth, rememberMe ? browserLocalPersistence : browserSessionPersistence);
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

  const handleChangePassword = async () => {
    setPasswordError('');
    setPasswordSuccess(false);
    if (!oldPassword || !newPassword || !confirmPassword) {
      setPasswordError('נא למלא את כל השדות');
      return;
    }
    if (newPassword.length < 6) {
      setPasswordError('סיסמה חדשה חייבת להיות לפחות 6 תווים');
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError('הסיסמאות החדשות אינן תואמות');
      return;
    }
    setIsChangingPassword(true);
    try {
      const res = await authFetch('/api/users/change-password', {
        method: 'POST',
        body: JSON.stringify({ oldPassword, newPassword }),
      });
      const data = await res.json();
      if (res.ok) {
        setPasswordSuccess(true);
        setOldPassword('');
        setNewPassword('');
        setConfirmPassword('');
        setTimeout(() => { setShowPasswordModal(false); setPasswordSuccess(false); }, 2000);
      } else {
        setPasswordError(data.error || 'שגיאה בשינוי סיסמה');
      }
    } catch {
      setPasswordError('שגיאה בתקשורת');
    }
    setIsChangingPassword(false);
  };

  const handleLogout = async () => {
    await signOut(auth);
    setIsAuthenticated(false);
    setUser(null);
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#F1E6D2] flex items-center justify-center" dir="rtl">
        <BookLoader />
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-[#F1E6D2] font-sans flex items-center justify-center p-6 relative overflow-hidden" dir="rtl">
        <div
          aria-hidden="true"
          className="absolute -top-20 -left-20 text-[500px] text-[#B14F1C]/[0.06] leading-none select-none"
          style={{ fontFamily: 'var(--font-serif)' }}
        >
          ה
        </div>
        <div className="bg-[#E8DCC4] border border-[#D6C8A8] w-full max-w-md p-8 sm:p-10 relative">
          <div className="text-xs tracking-[0.3em] font-bold text-[#B14F1C] mb-3 text-center">● מערכת ניהול</div>
          <h1 className="text-3xl sm:text-4xl font-serif font-semibold text-[#1F1A14] mb-8 text-center leading-tight">
            התחברות<span className="text-[#B14F1C]">.</span>
          </h1>
          {loginError && (
            <div className="border-r-4 border-[#B14F1C] bg-[#F1E6D2] px-4 py-2.5 mb-4 text-sm font-bold text-[#B14F1C]">{loginError}</div>
          )}
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-[#1F1A14] mb-1.5 tracking-wider uppercase">אימייל</label>
              <input type="email" value={loginEmail} onChange={(e) => setLoginEmail(e.target.value)}
                className="w-full p-3 border border-[#D6C8A8] bg-[#F1E6D2] focus:bg-white focus:border-[#B14F1C] focus:outline-none text-sm font-serif text-[#1F1A14]" placeholder="email@example.com" dir="ltr" />
            </div>
            <div>
              <label className="block text-xs font-bold text-[#1F1A14] mb-1.5 tracking-wider uppercase">סיסמה</label>
              <input type="password" value={loginPassword} onChange={(e) => setLoginPassword(e.target.value)}
                className="w-full p-3 border border-[#D6C8A8] bg-[#F1E6D2] focus:bg-white focus:border-[#B14F1C] focus:outline-none text-sm font-serif text-[#1F1A14]" placeholder="••••••••"
                onKeyDown={(e) => e.key === 'Enter' && handleLogin()} />
            </div>
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input type="checkbox" checked={rememberMe} onChange={(e) => setRememberMe(e.target.checked)}
                className="w-4 h-4 border-[#D6C8A8] text-[#B14F1C] focus:ring-[#B14F1C] cursor-pointer accent-[#B14F1C]" />
              <span className="text-sm text-[#6B5D4F] font-serif">זכור אותי</span>
            </label>
            <button onClick={handleLogin} disabled={isLoggingIn}
              className="w-full bg-[#1F1A14] text-[#F1E6D2] hover:bg-[#B14F1C] py-3.5 transition-colors font-bold mt-4 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed tracking-wider text-sm">
              {isLoggingIn && <Loader2 size={16} className="animate-spin" />}
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
      <div className="min-h-screen bg-[#F1E6D2] font-sans" dir="rtl">
        {/* Top dark strip — matches public site */}
        <div className="bg-[#1F1A14] text-[#F1E6D2] px-3 sm:px-6 py-2 flex justify-between items-center text-xs">
          <div className="flex items-center gap-3">
            <span className="font-serif text-sm">הראי״ה · <span className="text-[#B14F1C]">ניהול</span></span>
            <span className="hidden sm:inline opacity-60">/</span>
            <span className="hidden sm:inline opacity-80">{user?.name} · {roleName}</span>
          </div>
          <Link href="/" className="flex items-center gap-1.5 opacity-80 hover:opacity-100 hover:text-[#B14F1C] transition-colors">
            <BookOpen size={14} />
            <span>חזרה לאתר</span>
          </Link>
        </div>

        {/* Main top bar */}
        <header className="bg-[#E8DCC4] border-b-2 border-[#D6C8A8] px-3 sm:px-6 py-3 sticky top-0 z-50 relative">
          <div className="max-w-7xl mx-auto flex justify-between items-center gap-2">
            {/* Left: logout + password + bell */}
            <div className="flex items-center gap-1 sm:gap-2 shrink-0">
              <button onClick={handleLogout} title="התנתק" className="flex items-center gap-1.5 px-3 py-1.5 text-xs sm:text-sm text-[#B14F1C] hover:bg-[#F1E6D2] font-bold whitespace-nowrap tracking-wider transition-colors">
                <LogOut size={14} />
                <span className="hidden sm:inline">התנתק</span>
              </button>
              <button onClick={() => { setShowPasswordModal(true); setPasswordError(''); setPasswordSuccess(false); }} title="שנה סיסמה"
                className="p-2 hover:bg-[#F1E6D2] transition-colors">
                <Key size={16} className="text-[#1F1A14]" />
              </button>
              <button onClick={() => setShowAnnouncementsPopup(!showAnnouncementsPopup)}
                className="relative p-2 hover:bg-[#F1E6D2] transition-colors">
                <Bell size={16} className="text-[#1F1A14]" />
                {unreadAnnouncements.length > 0 && (
                  <span className="absolute top-0.5 right-0.5 bg-[#B14F1C] text-white text-[10px] font-bold w-4 h-4 rounded-full flex items-center justify-center">
                    {unreadAnnouncements.length > 9 ? '9+' : unreadAnnouncements.length}
                  </span>
                )}
              </button>
            </div>

            {/* Center: nav */}
            <nav className="flex bg-[#F1E6D2] border border-[#D6C8A8] overflow-x-auto">
              {navItems.filter(item => user && item.roles.includes(user.role)).map(item => (
                <Link key={item.href} href={item.href} title={item.label}
                  className={`relative flex items-center gap-1.5 px-3 sm:px-4 py-2 text-xs sm:text-sm font-bold transition-colors whitespace-nowrap tracking-wider ${pathname === item.href ? 'bg-[#1F1A14] text-[#F1E6D2]' : 'text-[#6B5D4F] hover:text-[#1F1A14] hover:bg-[#E8DCC4]'}`}>
                  <item.icon size={16} />
                  {'badge' in item && item.badge! > 0 && (
                    <span className="absolute -top-1 -right-1 bg-[#B14F1C] text-white text-[10px] font-bold w-4 h-4 rounded-full flex items-center justify-center">
                      {item.badge! > 99 ? '99+' : item.badge}
                    </span>
                  )}
                  <span className="hidden lg:inline">{item.label}</span>
                </Link>
              ))}
            </nav>

            {/* Right: home */}
            <div className="flex items-center gap-2 shrink-0">
              <Link href="/" className="flex items-center gap-1 p-2 hover:bg-[#F1E6D2] transition-colors" title="חזרה לאתר">
                <BookOpen size={20} className="text-[#B14F1C]" />
              </Link>
            </div>
          </div>

          {/* Announcements popup */}
          {showAnnouncementsPopup && (
            <div className="absolute left-6 top-16 w-96 max-h-[28rem] overflow-y-auto bg-[#E8DCC4] shadow-2xl border-2 border-[#D6C8A8] z-[100] p-4">
              <div className="flex justify-between items-center mb-4 pb-3 border-b border-[#D6C8A8]">
                <h3 className="font-serif text-lg text-[#1F1A14] flex items-center gap-2"><Bell size={16} className="text-[#B14F1C]" /> הודעות</h3>
                {unreadAnnouncements.length > 0 && (
                  <button onClick={dismissAllAnnouncements} className="text-xs text-[#B14F1C] hover:underline font-bold tracking-wider">סמן הכל כנקרא</button>
                )}
              </div>
              {unreadAnnouncements.length === 0 ? (
                <p className="text-center text-sm text-[#6B5D4F] py-6 font-serif italic">אין הודעות חדשות</p>
              ) : (
                <div className="space-y-3">
                  {unreadAnnouncements.map((a: any) => (
                    <div key={a.id} className="p-3 bg-[#F1E6D2] border-r-4 border-[#B14F1C]">
                      <div className="flex justify-between items-center mb-2">
                        <span className="font-bold text-sm text-[#1F1A14] font-serif">{a.title}</span>
                        <button onClick={() => markAnnouncementRead(a.id)} className="text-[#6B5D4F] hover:text-[#B14F1C] p-0.5">
                          <X size={14} />
                        </button>
                      </div>
                      <div className="text-sm text-[#1F1A14] leading-relaxed font-serif">
                        <SimpleMarkdown>{a.content}</SimpleMarkdown>
                      </div>
                      <div className="flex items-center justify-between mt-2 pt-2 border-t border-[#D6C8A8]">
                        <span className="text-xs text-[#6B5D4F]">{a.createdBy}</span>
                        <span className="text-xs text-[#6B5D4F]">{new Date(a.createdAt).toLocaleDateString('he-IL')}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </header>

        {/* Password Change Modal */}
        {showPasswordModal && (
          <div className="fixed inset-0 bg-[#1F1A14]/70 z-[200] flex items-center justify-center p-4" onClick={() => setShowPasswordModal(false)}>
            <div className="bg-[#E8DCC4] border-2 border-[#D6C8A8] w-full max-w-sm p-6" onClick={(e) => e.stopPropagation()}>
              <div className="flex justify-between items-center mb-5 pb-3 border-b border-[#D6C8A8]">
                <h3 className="font-serif text-xl text-[#1F1A14] flex items-center gap-2"><Key size={18} className="text-[#B14F1C]" /> שינוי סיסמה</h3>
                <button onClick={() => setShowPasswordModal(false)} className="p-1 text-[#6B5D4F] hover:text-[#B14F1C]"><X size={18} /></button>
              </div>
              {passwordError && <div className="border-r-4 border-[#B14F1C] bg-[#F1E6D2] px-3 py-2 mb-3 text-sm font-bold text-[#B14F1C]">{passwordError}</div>}
              {passwordSuccess && <div className="border-r-4 border-green-700 bg-[#F1E6D2] px-3 py-2 mb-3 text-sm font-bold text-green-800">הסיסמה שונתה בהצלחה!</div>}
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-bold text-[#1F1A14] mb-1.5 tracking-wider uppercase">סיסמה נוכחית</label>
                  <input type="password" value={oldPassword} onChange={(e) => setOldPassword(e.target.value)}
                    className="w-full p-2.5 border border-[#D6C8A8] bg-[#F1E6D2] focus:bg-white focus:border-[#B14F1C] focus:outline-none font-serif text-sm" placeholder="••••••••" />
                </div>
                <div>
                  <label className="block text-xs font-bold text-[#1F1A14] mb-1.5 tracking-wider uppercase">סיסמה חדשה</label>
                  <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)}
                    className="w-full p-2.5 border border-[#D6C8A8] bg-[#F1E6D2] focus:bg-white focus:border-[#B14F1C] focus:outline-none font-serif text-sm" placeholder="••••••••" />
                </div>
                <div>
                  <label className="block text-xs font-bold text-[#1F1A14] mb-1.5 tracking-wider uppercase">אימות סיסמה חדשה</label>
                  <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)}
                    className="w-full p-2.5 border border-[#D6C8A8] bg-[#F1E6D2] focus:bg-white focus:border-[#B14F1C] focus:outline-none font-serif text-sm" placeholder="••••••••"
                    onKeyDown={(e) => e.key === 'Enter' && handleChangePassword()} />
                </div>
                <button onClick={handleChangePassword} disabled={isChangingPassword}
                  className="w-full bg-[#1F1A14] text-[#F1E6D2] hover:bg-[#B14F1C] py-3 transition-colors font-bold flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed tracking-wider text-sm">
                  {isChangingPassword && <Loader2 size={16} className="animate-spin" />}
                  {isChangingPassword ? 'מעדכן...' : 'שנה סיסמה'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Content */}
        <main className="max-w-7xl mx-auto px-3 py-4 sm:p-6">
          {children}
        </main>
      </div>
    </AdminContext.Provider>
  );
}
