import { initializeApp, getApps, cert } from 'firebase-admin/app';
import { getAuth } from 'firebase-admin/auth';
import { getFirestore } from 'firebase-admin/firestore';
import { NextResponse } from 'next/server';

const serviceAccount = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT_KEY || '{}');

if (getApps().length === 0) {
  initializeApp({
    credential: cert(serviceAccount),
  });
}

export const adminAuth = getAuth();
export const adminDb = getFirestore();

// Cache user docs to avoid Firestore read on every authenticated request
const userCache = new Map<string, { data: any; expires: number }>();
const USER_CACHE_TTL = 5 * 60 * 1000; // 5 minutes

// Verify Firebase Auth token from request and return user data with role
export async function verifyAuth(request: Request): Promise<{
  uid: string;
  email: string;
  role: string;
  name: string;
} | null> {
  try {
    const authHeader = request.headers.get('Authorization');
    if (!authHeader?.startsWith('Bearer ')) return null;

    const token = authHeader.split('Bearer ')[1];
    const decoded = await adminAuth.verifyIdToken(token);

    // Check user cache first
    const cached = userCache.get(decoded.uid);
    if (cached && Date.now() < cached.expires) {
      return cached.data;
    }

    // Get user role from Firestore
    const userDoc = await adminDb.collection('users').doc(decoded.uid).get();
    if (!userDoc.exists) return null;

    const userData = userDoc.data()!;
    const result = {
      uid: decoded.uid,
      email: decoded.email || '',
      role: userData.role,
      name: userData.name,
    };

    userCache.set(decoded.uid, { data: result, expires: Date.now() + USER_CACHE_TTL });
    return result;
  } catch {
    return null;
  }
}

// Check if user has one of the required roles
export function hasRole(user: { role: string } | null, roles: string[]): boolean {
  return user !== null && roles.includes(user.role);
}

// Return 401 response
export function unauthorized() {
  return NextResponse.json({ error: 'לא מורשה' }, { status: 401 });
}

// Return 403 response
export function forbidden() {
  return NextResponse.json({ error: 'אין הרשאה לפעולה זו' }, { status: 403 });
}
