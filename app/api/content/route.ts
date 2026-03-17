import { NextResponse } from 'next/server';
import { adminDb, verifyAuth, hasRole, unauthorized, forbidden } from '@/lib/firebase-admin';

const CONTENT_DOC = 'content/main';

const defaultData = {
  book: 'אורות הקודש',
  seder: 'חלק א׳',
  chapter: 'פרק א׳',
  paragraphTitle: 'חכמת הקודש',
  isEdited: false,
  originalText: 'חכמת הקודש היא למעלה מכל חכמה. היא אינה רק ידיעה שכלית, אלא חיות פנימית המאירה את כל חדרי הנפש.',
  tags: 'קודש, חכמה, אורות',
  commentary: [
    { id: 1, text: 'הפסקה מדברת על ההבדל בין חכמה רגילה לחכמת הקודש.' }
  ],
  comments: [],
  questionsForRabbi: []
};

export async function GET() {
  try {
    const doc = await adminDb.doc(CONTENT_DOC).get();
    if (!doc.exists) {
      return NextResponse.json(defaultData);
    }
    return NextResponse.json(doc.data());
  } catch (error) {
    console.error('Content GET error:', error);
    return NextResponse.json(defaultData);
  }
}

export async function POST(request: Request) {
  const currentUser = await verifyAuth(request);
  if (!currentUser) return unauthorized();
  if (!hasRole(currentUser, ['admin', 'editor', 'rabbi'])) return forbidden();

  try {
    const data = await request.json();

    // Only admin and editor can update content
    // Rabbi can only update via specific endpoints (replies are part of comments)
    await adminDb.doc(CONTENT_DOC).set(data, { merge: true });

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Content POST error:', error);
    return NextResponse.json({ error: 'שגיאה בשמירת תוכן' }, { status: 500 });
  }
}
