import { NextResponse } from 'next/server';
import { adminDb, verifyAuth, hasRole, unauthorized, forbidden } from '@/lib/firebase-admin';
import { invalidateCache } from '@/lib/cache';

export async function PUT(request: Request) {
  const currentUser = await verifyAuth(request);
  if (!currentUser) return unauthorized();
  if (!hasRole(currentUser, ['admin'])) return forbidden();

  try {
    const { orderedIds } = await request.json();
    if (!Array.isArray(orderedIds) || orderedIds.length === 0) {
      return NextResponse.json({ error: 'orderedIds is required' }, { status: 400 });
    }

    const batch = adminDb.batch();
    orderedIds.forEach((id: string, index: number) => {
      batch.update(adminDb.collection('books').doc(id), { orderIndex: index });
    });
    await batch.commit();
    invalidateCache('books:');

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Books reorder error:', error);
    return NextResponse.json({ error: 'שגיאה בשינוי סדר' }, { status: 500 });
  }
}
