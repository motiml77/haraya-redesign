import { NextResponse } from 'next/server';
import { headers } from 'next/headers';
import { adminDb } from '@/lib/firebase-admin';
import { FieldValue } from 'firebase-admin/firestore';
import { getCached, setCache, invalidateCache } from '@/lib/cache';
import crypto from 'crypto';

const ANALYTICS_DOC = 'analytics/general';

export async function GET() {
  try {
    const cached = getCached<{ visitors: number }>('analytics:general');
    if (cached) return NextResponse.json(cached);

    const doc = await adminDb.doc(ANALYTICS_DOC).get();
    const result = { visitors: doc.exists ? (doc.data()?.visitors || 0) : 0 };
    setCache('analytics:general', result, 30_000);
    return NextResponse.json(result);
  } catch (error) {
    console.error('Analytics GET error:', error);
    return NextResponse.json({ visitors: 0 });
  }
}

export async function POST() {
  try {
    const headersList = await headers();
    const forwarded = headersList.get('x-forwarded-for');
    const ip = forwarded ? forwarded.split(',')[0].trim() : 'unknown';
    // Hash IP for privacy
    const ipHash = crypto.createHash('sha256').update(ip + '_rav_fudi').digest('hex').slice(0, 16);

    const docRef = adminDb.doc(ANALYTICS_DOC);
    const doc = await docRef.get();
    const data = doc.exists ? doc.data() : null;
    const visitedIps: string[] = data?.visitedIps || [];

    if (visitedIps.includes(ipHash)) {
      // Already counted this IP
      return NextResponse.json({ success: true, visitors: data?.visitors || 0, duplicate: true });
    }

    // New unique visitor
    if (!doc.exists) {
      await docRef.set({ visitors: 1, visitedIps: [ipHash] });
    } else {
      await docRef.update({
        visitors: FieldValue.increment(1),
        visitedIps: FieldValue.arrayUnion(ipHash),
      });
    }

    invalidateCache('analytics:');
    const updated = await docRef.get();
    return NextResponse.json({ success: true, visitors: updated.data()?.visitors || 0 });
  } catch (error) {
    console.error('Analytics POST error:', error);
    return NextResponse.json({ error: 'שגיאה בעדכון אנליטיקס' }, { status: 500 });
  }
}
