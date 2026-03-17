import { NextResponse } from 'next/server';
import { adminDb, verifyAuth, hasRole, unauthorized, forbidden } from '@/lib/firebase-admin';
import { FieldValue } from 'firebase-admin/firestore';
import { invalidateCache } from '@/lib/cache';

export async function PUT(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const currentUser = await verifyAuth(request);
  if (!currentUser) return unauthorized();

  try {
    const { action } = await request.json();

    if (action === 'markRead') {
      await adminDb.collection('announcements').doc(id).update({
        readBy: FieldValue.arrayUnion(currentUser.uid),
      });
      invalidateCache('announcements:');
      return NextResponse.json({ success: true });
    }

    return NextResponse.json({ error: 'פעולה לא ידועה' }, { status: 400 });
  } catch (error) {
    console.error('Announcement PUT error:', error);
    return NextResponse.json({ error: 'שגיאה בעדכון' }, { status: 500 });
  }
}

export async function DELETE(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const currentUser = await verifyAuth(request);
  if (!currentUser) return unauthorized();
  if (!hasRole(currentUser, ['admin'])) return forbidden();

  try {
    await adminDb.collection('announcements').doc(id).delete();
    invalidateCache('announcements:');
    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Announcement DELETE error:', error);
    return NextResponse.json({ error: 'שגיאה במחיקה' }, { status: 500 });
  }
}
