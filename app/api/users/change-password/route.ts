import { NextResponse } from 'next/server';
import { adminAuth, verifyAuth, unauthorized } from '@/lib/firebase-admin';

export async function POST(request: Request) {
  const currentUser = await verifyAuth(request);
  if (!currentUser) return unauthorized();

  const { oldPassword, newPassword } = await request.json();

  if (!oldPassword || !newPassword) {
    return NextResponse.json({ error: 'נא למלא את כל השדות' }, { status: 400 });
  }

  if (newPassword.length < 6) {
    return NextResponse.json({ error: 'סיסמה חדשה חייבת להיות לפחות 6 תווים' }, { status: 400 });
  }

  try {
    // Verify old password using Firebase Auth REST API
    const apiKey = process.env.NEXT_PUBLIC_FIREBASE_API_KEY;
    const signInRes = await fetch(
      `https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=${apiKey}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: currentUser.email,
          password: oldPassword,
          returnSecureToken: false,
        }),
      }
    );

    if (!signInRes.ok) {
      return NextResponse.json({ error: 'הסיסמה הנוכחית שגויה' }, { status: 400 });
    }

    // Update to new password
    await adminAuth.updateUser(currentUser.uid, { password: newPassword });
    return NextResponse.json({ success: true });
  } catch (error: any) {
    console.error('Change password error:', error.message);
    return NextResponse.json({ error: 'שגיאה בשינוי סיסמה' }, { status: 500 });
  }
}
