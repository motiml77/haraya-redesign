import { NextResponse } from 'next/server';
import { adminDb, verifyAuth, hasRole, unauthorized, forbidden } from '@/lib/firebase-admin';
import { invalidateCache } from '@/lib/cache';

// Public endpoint - anyone can add a comment
export async function POST(request: Request, { params }: { params: Promise<{ sectionId: string }> }) {
  const { sectionId } = await params;

  try {
    const { author, text } = await request.json();
    if (!author || !text) {
      return NextResponse.json({ error: 'שם ותגובה הם חובה' }, { status: 400 });
    }
    if (author.length > 100) {
      return NextResponse.json({ error: 'שם מחבר ארוך מדי (מקסימום 100 תווים)' }, { status: 400 });
    }
    if (text.length > 5000) {
      return NextResponse.json({ error: 'תגובה ארוכה מדי (מקסימום 5000 תווים)' }, { status: 400 });
    }

    const doc = await adminDb.collection('sections').doc(sectionId).get();
    if (!doc.exists) {
      return NextResponse.json({ error: 'חלק לא נמצא' }, { status: 404 });
    }

    const data = doc.data()!;
    const comments = data.comments || [];

    const newComment = {
      id: Date.now(),
      author,
      text,
      date: new Date().toISOString().split('T')[0],
      replies: [],
    };

    comments.push(newComment);

    await adminDb.collection('sections').doc(sectionId).update({ comments });

    invalidateCache(`sections:${sectionId}`);
    return NextResponse.json({ success: true, comment: newComment });
  } catch (error) {
    console.error('Comment POST error:', error);
    return NextResponse.json({ error: 'שגיאה בהוספת תגובה' }, { status: 500 });
  }
}

// Admin/Rabbi - edit a comment
export async function PUT(request: Request, { params }: { params: Promise<{ sectionId: string }> }) {
  const { sectionId } = await params;
  const currentUser = await verifyAuth(request);
  if (!currentUser) return unauthorized();
  if (!hasRole(currentUser, ['admin', 'rabbi'])) return forbidden();

  try {
    const { commentId, text } = await request.json();
    if (!commentId || !text) {
      return NextResponse.json({ error: 'חסרים נתונים' }, { status: 400 });
    }

    const doc = await adminDb.collection('sections').doc(sectionId).get();
    if (!doc.exists) {
      return NextResponse.json({ error: 'חלק לא נמצא' }, { status: 404 });
    }

    const data = doc.data()!;
    const comments = (data.comments || []).map((c: any) =>
      c.id === commentId ? { ...c, text, editedAt: new Date().toISOString().split('T')[0] } : c
    );

    await adminDb.collection('sections').doc(sectionId).update({ comments });

    invalidateCache(`sections:${sectionId}`);
    return NextResponse.json({ success: true, comments });
  } catch (error) {
    console.error('Comment PUT error:', error);
    return NextResponse.json({ error: 'שגיאה בעדכון תגובה' }, { status: 500 });
  }
}

// Admin/Rabbi - delete a comment
export async function DELETE(request: Request, { params }: { params: Promise<{ sectionId: string }> }) {
  const { sectionId } = await params;
  const currentUser = await verifyAuth(request);
  if (!currentUser) return unauthorized();
  if (!hasRole(currentUser, ['admin', 'rabbi'])) return forbidden();

  try {
    const { commentId } = await request.json();
    if (!commentId) {
      return NextResponse.json({ error: 'חסר מזהה תגובה' }, { status: 400 });
    }

    const doc = await adminDb.collection('sections').doc(sectionId).get();
    if (!doc.exists) {
      return NextResponse.json({ error: 'חלק לא נמצא' }, { status: 404 });
    }

    const data = doc.data()!;
    const comments = (data.comments || []).filter((c: any) => c.id !== commentId);

    await adminDb.collection('sections').doc(sectionId).update({ comments });

    invalidateCache(`sections:${sectionId}`);
    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Comment DELETE error:', error);
    return NextResponse.json({ error: 'שגיאה במחיקת תגובה' }, { status: 500 });
  }
}
