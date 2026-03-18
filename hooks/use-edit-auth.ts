import { useState, useEffect } from 'react';
import { onAuthStateChanged } from 'firebase/auth';
import { auth } from '@/lib/firebase';

interface EditUser {
  id: string;
  role: string;
  name: string;
}

const EDIT_ROLES = ['admin', 'editor', 'rabbi'];

export function useEditAuth() {
  const [user, setUser] = useState<EditUser | null>(null);
  const [canEdit, setCanEdit] = useState(false);
  const [loading, setLoading] = useState(true);

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
          if (data.success && EDIT_ROLES.includes(data.user.role)) {
            setUser({ id: data.user.id, role: data.user.role, name: data.user.name });
            setCanEdit(true);
          } else {
            setUser(null);
            setCanEdit(false);
          }
        } catch {
          setUser(null);
          setCanEdit(false);
        }
      } else {
        setUser(null);
        setCanEdit(false);
      }
      setLoading(false);
    });
    return () => unsubscribe();
  }, []);

  return { user, canEdit, loading };
}
