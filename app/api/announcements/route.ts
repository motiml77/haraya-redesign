import { NextResponse } from 'next/server';
import { adminDb, verifyAuth, hasRole, unauthorized, forbidden } from '@/lib/firebase-admin';
import { getCached, setCache, invalidateCache } from '@/lib/cache';

export async function GET(request: Request) {
  try {
    const url = new URL(request.url);
    const type = url.searchParams.get('type');
    const unreadFor = url.searchParams.get('unreadFor');

    // Cache base queries (without unreadFor which is user-specific filtering)
    const cacheKey = `announcements:${type || 'all'}`;
    let announcements: any[];

    const cached = getCached<any[]>(cacheKey);
    if (cached) {
      announcements = cached;
    } else {
      let query: FirebaseFirestore.Query = adminDb.collection('announcements').orderBy('createdAt', 'desc');
      if (type) {
        query = query.where('type', '==', type);
      }
      const snapshot = await query.limit(50).get();
      announcements = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
      setCache(cacheKey, announcements, 60_000); // 1 minute cache
    }

    if (unreadFor) {
      announcements = announcements.filter((a: any) =>
        !a.readBy || !a.readBy.includes(unreadFor)
      );
    }

    return NextResponse.json(announcements);
  } catch (error) {
    console.error('Announcements GET error:', error);
    return NextResponse.json([]);
  }
}

export async function POST(request: Request) {
  const currentUser = await verifyAuth(request);
  if (!currentUser) return unauthorized();
  if (!hasRole(currentUser, ['admin', 'rabbi'])) return forbidden();

  try {
    const { title, content, type } = await request.json();
    if (!title || !content || !type) {
      return NextResponse.json({ error: 'כל השדות הם חובה' }, { status: 400 });
    }
    if (!['editors', 'all'].includes(type)) {
      return NextResponse.json({ error: 'סוג הודעה לא תקין' }, { status: 400 });
    }

    const doc = await adminDb.collection('announcements').add({
      title,
      content,
      type,
      createdBy: currentUser.name,
      createdByUid: currentUser.uid,
      createdAt: new Date().toISOString(),
      readBy: [],
    });

    invalidateCache('announcements:');
    return NextResponse.json({ success: true, id: doc.id });
  } catch (error) {
    console.error('Announcements POST error:', error);
    return NextResponse.json({ error: 'שגיאה ביצירת הודעה' }, { status: 500 });
  }
}
