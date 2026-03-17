import { NextResponse } from 'next/server';
import { adminDb, verifyAuth, hasRole, unauthorized, forbidden } from '@/lib/firebase-admin';
import { getCached, setCache } from '@/lib/cache';

// Get all questions across all sections (for rabbi dashboard)
// Cached for 2 minutes to avoid full collection scan on every request
export async function GET(request: Request) {
  const currentUser = await verifyAuth(request);
  if (!currentUser) return unauthorized();
  if (!hasRole(currentUser, ['admin', 'rabbi'])) return forbidden();

  const url = new URL(request.url);
  const includeResolved = url.searchParams.get('includeResolved') === 'true';
  const cacheKey = `questions:${includeResolved ? 'all' : 'unresolved'}`;

  try {
    const cached = getCached<any>(cacheKey);
    if (cached) return NextResponse.json(cached);

    const snapshot = await adminDb.collection('sections').get();

    const allQuestions: any[] = [];
    const unansweredComments: any[] = [];
    const resolvedComments: any[] = [];

    for (const doc of snapshot.docs) {
      const data = doc.data();
      const sectionId = doc.id;

      if (data.questionsForRabbi && data.questionsForRabbi.length > 0) {
        for (const q of data.questionsForRabbi) {
          if (!includeResolved && q.resolved) continue;
          allQuestions.push({
            ...q,
            sectionId,
            sectionTitle: data.title,
            bookTitle: data.bookTitle,
            bookId: data.bookId,
          });
        }
      }

      if (data.comments) {
        for (const c of data.comments) {
          if ((!c.replies || c.replies.length === 0) && !c.resolved) {
            unansweredComments.push({
              ...c,
              sectionId,
              sectionTitle: data.title,
              bookTitle: data.bookTitle,
              bookId: data.bookId,
            });
          } else if (includeResolved && (c.resolved || (c.replies && c.replies.length > 0))) {
            resolvedComments.push({
              ...c,
              sectionId,
              sectionTitle: data.title,
              bookTitle: data.bookTitle,
              bookId: data.bookId,
            });
          }
        }
      }
    }

    const result = { questions: allQuestions, unansweredComments, resolvedComments };
    setCache(cacheKey, result, 120_000); // 2 minute cache
    return NextResponse.json(result);
  } catch (error) {
    console.error('Questions GET error:', error);
    return NextResponse.json({ questions: [], unansweredComments: [] });
  }
}
