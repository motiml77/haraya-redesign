import { NextResponse } from 'next/server';
import { adminDb, verifyAuth, hasRole, unauthorized, forbidden } from '@/lib/firebase-admin';
import { getCached, setCache, invalidateCache } from '@/lib/cache';

// Public endpoint - anyone can submit a contact message
export async function POST(request: Request) {
  try {
    const { name, email, subject, message } = await request.json();
    if (!name || !message) {
      return NextResponse.json({ error: 'שם והודעה הם חובה' }, { status: 400 });
    }

    const newMessage = {
      name,
      email: email || '',
      subject: subject || '',
      message,
      date: new Date().toISOString().split('T')[0],
      createdAt: new Date().toISOString(),
      replies: [],
      resolved: false,
    };

    await adminDb.collection('contactMessages').add(newMessage);
    invalidateCache('contact:');
    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Contact POST error:', error);
    return NextResponse.json({ error: 'שגיאה בשליחת ההודעה' }, { status: 500 });
  }
}

// Admin/Rabbi - get contact messages
export async function GET(request: Request) {
  const currentUser = await verifyAuth(request);
  if (!currentUser) return unauthorized();
  if (!hasRole(currentUser, ['admin', 'rabbi'])) return forbidden();

  const url = new URL(request.url);
  const includeResolved = url.searchParams.get('includeResolved') === 'true';
  const cacheKey = includeResolved ? 'contact:all' : 'contact:unresolved';

  try {
    const cached = getCached<any[]>(cacheKey);
    if (cached) return NextResponse.json(cached);

    let query: FirebaseFirestore.Query = adminDb.collection('contactMessages');
    if (!includeResolved) {
      query = query.where('resolved', '==', false);
    }
    const snapshot = await query.get();

    const messages = snapshot.docs
      .map(doc => ({ id: doc.id, ...doc.data() }))
      .sort((a: any, b: any) => {
        const aTime = a.createdAt || '';
        const bTime = b.createdAt || '';
        return bTime > aTime ? 1 : bTime < aTime ? -1 : 0;
      });
    setCache(cacheKey, messages, 60_000);
    return NextResponse.json(messages);
  } catch (error) {
    console.error('Contact GET error:', error);
    return NextResponse.json([]);
  }
}
