'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { User, LogIn } from 'lucide-react';
import { onAuthStateChanged } from 'firebase/auth';
import { auth } from '@/lib/firebase';

export function PageHeaderAuth() {
  const [userName, setUserName] = useState<string | null>(null);
  const [authReady, setAuthReady] = useState(false);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
      setUserName(firebaseUser?.displayName || null);
      setAuthReady(true);
    });
    return () => unsubscribe();
  }, []);

  if (!authReady) return null;

  return (
    <Link href="/admin"
      className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full bg-[#E5C547] text-[#1F1A14] font-bold hover:bg-[#F1E6D2] transition-colors">
      {userName ? <User size={13} /> : <LogIn size={13} />}
      {userName || 'כניסת מנהלים'}
    </Link>
  );
}
