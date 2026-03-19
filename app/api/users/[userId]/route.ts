import { NextResponse } from 'next/server';
import { adminAuth, adminDb, verifyAuth, hasRole, unauthorized, forbidden } from '@/lib/firebase-admin';
import { invalidateCache } from '@/lib/cache';

export async function PUT(request: Request, { params }: { params: Promise<{ userId: string }> }) {
  const currentUser = await verifyAuth(request);
  if (!currentUser) return unauthorized();
  if (!hasRole(currentUser, ['admin'])) return forbidden();

  const { userId } = await params;
  const body = await request.json();

  try {
    // Update role
    if (body.role) {
      if (!['admin', 'editor', 'rabbi'].includes(body.role)) {
        return NextResponse.json({ error: 'תפקיד לא תקין' }, { status: 400 });
      }
      await adminDb.collection('users').doc(userId).update({ role: body.role });
      invalidateCache('users:');
      return NextResponse.json({ success: true, action: 'role_updated' });
    }

    // Reset password (admin sets new password)
    if (body.password) {
      if (body.password.length < 6) {
        return NextResponse.json({ error: 'סיסמה חייבת להיות לפחות 6 תווים' }, { status: 400 });
      }
      await adminAuth.updateUser(userId, { password: body.password });
      return NextResponse.json({ success: true, action: 'password_reset' });
    }

    return NextResponse.json({ error: 'לא צוינה פעולה' }, { status: 400 });
  } catch (error: any) {
    console.error('Update user error:', error.message);
    return NextResponse.json({ error: 'שגיאה בעדכון משתמש' }, { status: 500 });
  }
}

export async function DELETE(request: Request, { params }: { params: Promise<{ userId: string }> }) {
  const currentUser = await verifyAuth(request);
  if (!currentUser) return unauthorized();
  if (!hasRole(currentUser, ['admin'])) return forbidden();

  const { userId } = await params;

  // Prevent self-deletion
  if (userId === currentUser.uid) {
    return NextResponse.json({ error: 'לא ניתן למחוק את עצמך' }, { status: 400 });
  }

  try {
    await adminAuth.deleteUser(userId);
    await adminDb.collection('users').doc(userId).delete();
    invalidateCache('users:');
    return NextResponse.json({ success: true });
  } catch (error: any) {
    console.error('Delete user error:', error.message);
    return NextResponse.json({ error: 'שגיאה במחיקת משתמש' }, { status: 500 });
  }
}
