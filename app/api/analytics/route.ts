import { NextResponse } from 'next/server';
import { adminDb } from '@/lib/firebase-admin';
import { FieldValue } from 'firebase-admin/firestore';
import { getCached, setCache, invalidateCache } from '@/lib/cache';

const ANALYTICS_DOC = 'analytics/general';

export async function GET() {
  try {
    const cached = getCached<{ visitors: number }>('analytics:general');
    if (cached) return NextResponse.json(cached);

    const doc = await adminDb.doc(ANALYTICS_DOC).get();
    const result = { visitors: doc.exists ? (doc.data()?.visitors || 0) : 0 };
    setCache('analytics:general', result, 30_000); // 30 second cache
    return NextResponse.json(result);
  } catch (error) {
    console.error('Analytics GET error:', error);
    return NextResponse.json({ visitors: 0 });
  }
}

export async function POST() {
  try {
    const docRef = adminDb.doc(ANALYTICS_DOC);
    const doc = await docRef.get();

    if (!doc.exists) {
      await docRef.set({ visitors: 1 });
    } else {
      await docRef.update({ visitors: FieldValue.increment(1) });
    }

    invalidateCache('analytics:');
    const updated = await docRef.get();
    return NextResponse.json({ success: true, visitors: updated.data()?.visitors || 0 });
  } catch (error) {
    console.error('Analytics POST error:', error);
    return NextResponse.json({ error: 'שגיאה בעדכון אנליטיקס' }, { status: 500 });
  }
}
