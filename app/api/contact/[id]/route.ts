import { NextResponse } from 'next/server';
import { adminDb, verifyAuth, hasRole, unauthorized, forbidden } from '@/lib/firebase-admin';
import { invalidateCache } from '@/lib/cache';

// Admin/Rabbi - update a contact message (reply or resolve)
export async function PUT(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const currentUser = await verifyAuth(request);
  if (!currentUser) return unauthorized();
  if (!hasRole(currentUser, ['admin', 'rabbi'])) return forbidden();

  try {
    const body = await request.json();
    const docRef = adminDb.collection('contactMessages').doc(id);
    const doc = await docRef.get();
    if (!doc.exists) {
      return NextResponse.json({ error: 'הודעה לא נמצאה' }, { status: 404 });
    }

    const data = doc.data()!;

    // Add reply
    if (body.reply) {
      const replies = data.replies || [];
      const newReply: any = {
        id: Date.now(),
        author: body.reply.author,
        date: new Date().toISOString().split('T')[0],
        text: body.reply.text || '',
      };
      if (body.reply.audioUrl && typeof body.reply.audioUrl === 'string' && body.reply.audioUrl.startsWith('https://')) {
        newReply.audioUrl = body.reply.audioUrl;
      }
      if (Array.isArray(body.reply.attachments) && body.reply.attachments.length > 0) {
        newReply.attachments = body.reply.attachments.filter((a: any) =>
          a && typeof a.url === 'string' && a.url.startsWith('https://') &&
          typeof a.name === 'string' && ['pdf', 'docx', 'image'].includes(a.type) &&
          typeof a.size === 'number'
        );
      }
      replies.push(newReply);
      await docRef.update({ replies });
    }

    // Mark as resolved
    if (body.resolved) {
      await docRef.update({
        resolved: true,
        resolvedBy: body.resolvedBy || '',
        resolvedDate: new Date().toISOString().split('T')[0],
      });
    }

    invalidateCache('contact:');
    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Contact PUT error:', error);
    return NextResponse.json({ error: 'שגיאה בעדכון ההודעה' }, { status: 500 });
  }
}
