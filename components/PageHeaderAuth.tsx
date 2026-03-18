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
      className="flex items-center gap-1.5 text-xs text-[#8C7A6B] hover:text-[#8C2B2B] transition-colors px-3 py-1.5 rounded-full border border-[#E5E0D8] hover:border-[#8C2B2B] bg-[#FAF8F5]">
      {userName ? <User size={14} /> : <LogIn size={14} />}
      {userName || 'כניסת מנהלים'}
    </Link>
  );
}
