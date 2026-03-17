import { auth } from '@/lib/firebase';

export async function getIdToken(): Promise<string | null> {
  const user = auth.currentUser;
  if (!user) return null;
  return user.getIdToken();
}

export async function authFetch(url: string, options: RequestInit = {}) {
  const token = await getIdToken();
  if (!token) throw new Error('לא מחובר');

  return fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });
}
