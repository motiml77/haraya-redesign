import { NextResponse } from 'next/server';
import { adminDb, verifyAuth, hasRole, unauthorized, forbidden } from '@/lib/firebase-admin';
import { getCached, setCache, invalidateCache } from '@/lib/cache';

const CACHE_HEADERS = { 'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=120' };

export async function GET() {
  try {
    const cached = getCached<any[]>('books:list');
    if (cached) {
      return NextResponse.json(cached, { headers: CACHE_HEADERS });
    }

    const snapshot = await adminDb.collection('books').orderBy('orderIndex').get();
    const books = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));

    setCache('books:list', books, 60_000);
    return NextResponse.json(books, { headers: CACHE_HEADERS });
  } catch (error) {
    console.error('Books GET error:', error);
    return NextResponse.json([]);
  }
}

export async function POST(request: Request) {
  const currentUser = await verifyAuth(request);
  if (!currentUser) return unauthorized();
  if (!hasRole(currentUser, ['admin'])) return forbidden();

  try {
    const { title, description } = await request.json();
    if (!title) {
      return NextResponse.json({ error: 'שם הספר הוא חובה' }, { status: 400 });
    }

    // Get next orderIndex
    const last = await adminDb.collection('books').orderBy('orderIndex', 'desc').limit(1).get();
    const orderIndex = last.empty ? 0 : (last.docs[0].data().orderIndex || 0) + 1;

    const docRef = await adminDb.collection('books').add({
      title,
      description: description || '',
      orderIndex,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });

    invalidateCache('books:');
    return NextResponse.json({ success: true, id: docRef.id });
  } catch (error) {
    console.error('Books POST error:', error);
    return NextResponse.json({ error: 'שגיאה ביצירת ספר' }, { status: 500 });
  }
}
