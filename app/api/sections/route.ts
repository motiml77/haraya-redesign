import { NextResponse } from 'next/server';
import { adminDb, verifyAuth, hasRole, unauthorized, forbidden } from '@/lib/firebase-admin';
import { getCached, setCache, invalidateCache } from '@/lib/cache';

const CACHE_HEADERS = { 'Cache-Control': 'public, s-maxage=30, stale-while-revalidate=60' };

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const bookId = searchParams.get('bookId');
  const tag = searchParams.get('tag');

  try {
    const cacheKey = `sections:list:${bookId || 'all'}:${tag || ''}`;
    const cached = getCached<any[]>(cacheKey);
    if (cached) {
      return NextResponse.json(cached, { headers: CACHE_HEADERS });
    }

    let query: FirebaseFirestore.Query = adminDb.collection('sections');

    if (bookId) {
      query = query.where('bookId', '==', bookId);
    }

    if (tag) {
      query = query.where('tags', 'array-contains', tag);
    }

    const snapshot = await query.get();
    const sections = snapshot.docs.map(doc => ({
      id: doc.id,
      title: doc.data().title,
      bookId: doc.data().bookId,
      parentId: doc.data().parentId,
      depth: doc.data().depth,
      bookTitle: doc.data().bookTitle,
      isEdited: doc.data().isEdited,
      tags: doc.data().tags,
      orderIndex: doc.data().orderIndex,
      hasContent: !!(doc.data().originalText),
    })).sort((a, b) => (a.orderIndex || 0) - (b.orderIndex || 0));

    setCache(cacheKey, sections, 30_000);
    return NextResponse.json(sections, { headers: CACHE_HEADERS });
  } catch (error) {
    console.error('Sections GET error:', error);
    return NextResponse.json([]);
  }
}

export async function POST(request: Request) {
  const currentUser = await verifyAuth(request);
  if (!currentUser) return unauthorized();
  if (!hasRole(currentUser, ['admin', 'editor', 'rabbi'])) return forbidden();

  try {
    const { bookId, parentId, title } = await request.json();
    if (!bookId || !title) {
      return NextResponse.json({ error: 'ספר וכותרת הם חובה' }, { status: 400 });
    }

    // Calculate depth and orderIndex
    let depth = 0;
    if (parentId) {
      const parentDoc = await adminDb.collection('sections').doc(parentId).get();
      if (parentDoc.exists) {
        depth = (parentDoc.data()!.depth || 0) + 1;
      }
    }

    // Get max orderIndex among siblings
    const siblingsQuery = parentId
      ? adminDb.collection('sections').where('bookId', '==', bookId).where('parentId', '==', parentId)
      : adminDb.collection('sections').where('bookId', '==', bookId).where('parentId', '==', null);
    const siblings = await siblingsQuery.get();
    let orderIndex = 0;
    siblings.docs.forEach(d => {
      const idx = d.data().orderIndex || 0;
      if (idx >= orderIndex) orderIndex = idx + 1;
    });

    // Get book title for denormalization
    const bookDoc = await adminDb.collection('books').doc(bookId).get();
    const bookTitle = bookDoc.exists ? bookDoc.data()!.title : '';

    const docRef = await adminDb.collection('sections').add({
      bookId,
      parentId: parentId || null,
      title,
      orderIndex,
      depth,
      bookTitle,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });

    invalidateCache('sections:');
    invalidateCache('books:');
    return NextResponse.json({ success: true, id: docRef.id });
  } catch (error) {
    console.error('Sections POST error:', error);
    return NextResponse.json({ error: 'שגיאה ביצירת חלק' }, { status: 500 });
  }
}
