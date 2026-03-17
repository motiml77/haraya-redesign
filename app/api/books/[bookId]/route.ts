import { NextResponse } from 'next/server';
import { adminDb, verifyAuth, hasRole, unauthorized, forbidden } from '@/lib/firebase-admin';
import { getCached, setCache, invalidateCache } from '@/lib/cache';

const CACHE_HEADERS = { 'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=120' };

export async function GET(request: Request, { params }: { params: Promise<{ bookId: string }> }) {
  const { bookId } = await params;
  try {
    const cached = getCached<any>(`books:${bookId}`);
    if (cached) {
      return NextResponse.json(cached, { headers: CACHE_HEADERS });
    }

    // Run book + sections queries in parallel
    const [doc, sectionsSnap] = await Promise.all([
      adminDb.collection('books').doc(bookId).get(),
      adminDb.collection('sections').where('bookId', '==', bookId).get(),
    ]);

    if (!doc.exists) {
      return NextResponse.json({ error: 'ספר לא נמצא' }, { status: 404 });
    }

    const sections = sectionsSnap.docs.map(d => ({
      id: d.id,
      ...d.data(),
      hasContent: !!(d.data().originalText),
    })).sort((a: any, b: any) => (a.orderIndex || 0) - (b.orderIndex || 0));

    const result = { id: doc.id, ...doc.data(), sections };
    setCache(`books:${bookId}`, result, 60_000);
    return NextResponse.json(result, { headers: CACHE_HEADERS });
  } catch (error) {
    console.error('Book GET error:', error);
    return NextResponse.json({ error: 'שגיאה בטעינת ספר' }, { status: 500 });
  }
}

export async function PUT(request: Request, { params }: { params: Promise<{ bookId: string }> }) {
  const { bookId } = await params;
  const currentUser = await verifyAuth(request);
  if (!currentUser) return unauthorized();
  if (!hasRole(currentUser, ['admin'])) return forbidden();

  try {
    const data = await request.json();
    await adminDb.collection('books').doc(bookId).update({
      ...data,
      updatedAt: new Date().toISOString(),
    });
    invalidateCache('books:');
    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Book PUT error:', error);
    return NextResponse.json({ error: 'שגיאה בעדכון ספר' }, { status: 500 });
  }
}

export async function DELETE(request: Request, { params }: { params: Promise<{ bookId: string }> }) {
  const { bookId } = await params;
  const currentUser = await verifyAuth(request);
  if (!currentUser) return unauthorized();
  if (!hasRole(currentUser, ['admin'])) return forbidden();

  try {
    const sections = await adminDb.collection('sections').where('bookId', '==', bookId).limit(1).get();
    if (!sections.empty) {
      return NextResponse.json({ error: 'לא ניתן למחוק ספר שיש בו תוכן. מחק את התוכן קודם' }, { status: 400 });
    }

    await adminDb.collection('books').doc(bookId).delete();
    invalidateCache('books:');
    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Book DELETE error:', error);
    return NextResponse.json({ error: 'שגיאה במחיקת ספר' }, { status: 500 });
  }
}
