import { NextResponse } from 'next/server';
import { adminDb, verifyAuth, hasRole, unauthorized, forbidden } from '@/lib/firebase-admin';
import { getCached, setCache, invalidateCache } from '@/lib/cache';
import { normalizeSectionContent } from '@/lib/normalize-section';

const CACHE_HEADERS = { 'Cache-Control': 'public, s-maxage=30, stale-while-revalidate=60' };

export async function GET(request: Request, { params }: { params: Promise<{ sectionId: string }> }) {
  const { sectionId } = await params;
  try {
    const cached = getCached<any>(`sections:${sectionId}`);
    if (cached) {
      return NextResponse.json(cached, { headers: CACHE_HEADERS });
    }

    const doc = await adminDb.collection('sections').doc(sectionId).get();
    if (!doc.exists) {
      return NextResponse.json({ error: 'חלק לא נמצא' }, { status: 404 });
    }

    const result = normalizeSectionContent({ id: doc.id, ...doc.data() });
    setCache(`sections:${sectionId}`, result, 30_000);
    return NextResponse.json(result, { headers: CACHE_HEADERS });
  } catch (error) {
    console.error('Section GET error:', error);
    return NextResponse.json({ error: 'שגיאה בטעינת חלק' }, { status: 500 });
  }
}

export async function PUT(request: Request, { params }: { params: Promise<{ sectionId: string }> }) {
  const { sectionId } = await params;
  const currentUser = await verifyAuth(request);
  if (!currentUser) return unauthorized();
  if (!hasRole(currentUser, ['admin', 'editor', 'rabbi'])) return forbidden();

  try {
    const body = await request.json();

    // Whitelist allowed fields
    const allowedFields = ['title', 'tags', 'originalText', 'contentBlocks', 'bookId', 'parentSectionId', 'orderIndex', 'introduction', 'comments', 'questionsForRabbi'];
    const data: Record<string, any> = {};
    for (const key of allowedFields) {
      if (key in body) data[key] = body[key];
    }

    // Ensure tags is array
    if (data.tags && typeof data.tags === 'string') {
      data.tags = data.tags.split(',').map((t: string) => t.trim()).filter(Boolean);
    }

    // When saving contentBlocks, clear legacy fields
    if (data.contentBlocks && data.contentBlocks.length > 0) {
      data.originalText = '';
      data.commentary = [];
    }

    await adminDb.collection('sections').doc(sectionId).update({
      ...data,
      updatedAt: new Date().toISOString(),
    });

    invalidateCache(`sections:${sectionId}`);
    invalidateCache('sections:list:');
    invalidateCache('books:');
    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Section PUT error:', error);
    return NextResponse.json({ error: 'שגיאה בעדכון חלק' }, { status: 500 });
  }
}

export async function DELETE(request: Request, { params }: { params: Promise<{ sectionId: string }> }) {
  const { sectionId } = await params;
  const currentUser = await verifyAuth(request);
  if (!currentUser) return unauthorized();
  if (!hasRole(currentUser, ['admin'])) return forbidden();

  try {
    const doc = await adminDb.collection('sections').doc(sectionId).get();
    if (!doc.exists) {
      return NextResponse.json({ error: 'חלק לא נמצא' }, { status: 404 });
    }

    const bookId = doc.data()!.bookId;

    // Find all descendants by loading all sections for this book and building tree
    const allSections = await adminDb.collection('sections').where('bookId', '==', bookId).get();
    const toDelete: string[] = [sectionId];

    // Recursively find all descendants
    const findDescendants = (parentId: string) => {
      allSections.docs.forEach(d => {
        if (d.data().parentId === parentId) {
          toDelete.push(d.id);
          findDescendants(d.id);
        }
      });
    };
    findDescendants(sectionId);

    // Batch delete all
    const batch = adminDb.batch();
    toDelete.forEach(id => {
      batch.delete(adminDb.collection('sections').doc(id));
      invalidateCache(`sections:${id}`);
    });
    await batch.commit();

    invalidateCache('sections:');
    invalidateCache('books:');
    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Section DELETE error:', error);
    return NextResponse.json({ error: 'שגיאה במחיקת חלק' }, { status: 500 });
  }
}
