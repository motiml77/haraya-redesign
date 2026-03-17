import { NextResponse } from 'next/server';
import { adminAuth, adminDb, verifyAuth, hasRole, unauthorized, forbidden } from '@/lib/firebase-admin';
import { getCached, setCache, invalidateCache } from '@/lib/cache';

export async function GET(request: Request) {
  const currentUser = await verifyAuth(request);
  if (!currentUser) return unauthorized();
  if (!hasRole(currentUser, ['admin'])) return forbidden();

  try {
    const cached = getCached<any[]>('users:all');
    if (cached) return NextResponse.json(cached);

    const snapshot = await adminDb.collection('users').get();
    const users = snapshot.docs.map(doc => ({
      id: doc.id,
      email: doc.data().email,
      role: doc.data().role,
      name: doc.data().name,
    }));
    setCache('users:all', users, 60_000); // 1 minute cache
    return NextResponse.json(users);
  } catch (error) {
    return NextResponse.json({ error: 'שגיאה בטעינת משתמשים' }, { status: 500 });
  }
}

export async function POST(request: Request) {
  const currentUser = await verifyAuth(request);
  if (!currentUser) return unauthorized();
  if (!hasRole(currentUser, ['admin'])) return forbidden();

  try {
    const { name, email, password, role } = await request.json();

    if (!name || !email || !password || !role) {
      return NextResponse.json({ error: 'כל השדות הם חובה' }, { status: 400 });
    }

    if (!['admin', 'editor', 'rabbi'].includes(role)) {
      return NextResponse.json({ error: 'תפקיד לא תקין' }, { status: 400 });
    }

    // Create user in Firebase Auth
    const userRecord = await adminAuth.createUser({
      email,
      password,
      displayName: name,
    });

    // Save role and name in Firestore
    await adminDb.collection('users').doc(userRecord.uid).set({
      email,
      name,
      role,
      createdAt: new Date().toISOString(),
      createdBy: currentUser.uid,
    });

    invalidateCache('users:');
    return NextResponse.json({ success: true, id: userRecord.uid });
  } catch (error: any) {
    if (error.code === 'auth/email-already-exists') {
      return NextResponse.json({ error: 'כתובת אימייל כבר קיימת' }, { status: 400 });
    }
    console.error('Create user error:', error.message);
    return NextResponse.json({ error: 'שגיאה ביצירת משתמש' }, { status: 500 });
  }
}
