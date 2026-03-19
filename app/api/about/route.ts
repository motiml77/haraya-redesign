import { NextResponse } from 'next/server';
import { adminDb, verifyAuth, hasRole, unauthorized, forbidden } from '@/lib/firebase-admin';
import { getCached, setCache, invalidateCache } from '@/lib/cache';

const CACHE_HEADERS = { 'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=120' };

export async function GET() {
  try {
    const cached = getCached<any>('about:main');
    if (cached) {
      return NextResponse.json(cached, { headers: CACHE_HEADERS });
    }

    const doc = await adminDb.collection('about').doc('main').get();
    const data = doc.exists
      ? { id: doc.id, ...doc.data() }
      : { title: '', content: '', imageUrl: '' };

    setCache('about:main', data, 60_000);
    return NextResponse.json(data, { headers: CACHE_HEADERS });
  } catch (error) {
    console.error('About GET error:', error);
    return NextResponse.json({ title: '', content: '', imageUrl: '' });
  }
}

export async function PUT(request: Request) {
  const currentUser = await verifyAuth(request);
  if (!currentUser) return unauthorized();
  if (!hasRole(currentUser, ['admin'])) return forbidden();

  try {
    const { title, content, imageUrl } = await request.json();

    if (imageUrl && !imageUrl.startsWith('https://')) {
      return NextResponse.json({ error: 'כתובת תמונה חייבת להתחיל ב-https://' }, { status: 400 });
    }

    await adminDb.collection('about').doc('main').set({
      title: title || '',
      content: content || '',
      imageUrl: imageUrl || '',
      updatedAt: new Date().toISOString(),
      updatedBy: currentUser.uid,
    }, { merge: true });

    invalidateCache('about:');
    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('About PUT error:', error);
    return NextResponse.json({ error: 'שגיאה בעדכון דף אודות' }, { status: 500 });
  }
}
