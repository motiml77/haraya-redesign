import { NextResponse } from 'next/server';
import { adminAuth, adminDb } from '@/lib/firebase-admin';

export async function POST(request: Request) {
  try {
    const { idToken } = await request.json();

    // Verify the Firebase ID token sent from the client
    const decoded = await adminAuth.verifyIdToken(idToken);

    // Get user role from Firestore
    const userDoc = await adminDb.collection('users').doc(decoded.uid).get();

    if (!userDoc.exists) {
      return NextResponse.json({ success: false, error: 'משתמש לא נמצא במערכת' }, { status: 403 });
    }

    const userData = userDoc.data()!;

    return NextResponse.json({
      success: true,
      user: {
        id: decoded.uid,
        email: decoded.email,
        role: userData.role,
        name: userData.name,
      }
    });
  } catch (error: any) {
    console.error('Auth error:', error.message);
    return NextResponse.json({ success: false, error: 'שגיאה באימות' }, { status: 401 });
  }
}
