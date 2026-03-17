import { NextResponse } from 'next/server';
import { adminDb } from '@/lib/firebase-admin';
import { getCached, setCache } from '@/lib/cache';

const CACHE_HEADERS = { 'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=120' };

export async function GET() {
  try {
    const cacheKey = 'tags:all';
    const cached = getCached<any[]>(cacheKey);
    if (cached) {
      return NextResponse.json(cached, { headers: CACHE_HEADERS });
    }

    const snapshot = await adminDb.collection('sections').get();
    const tagMap = new Map<string, { count: number; sections: { id: string; title: string; bookTitle: string; bookId: string }[] }>();

    snapshot.docs.forEach(doc => {
      const data = doc.data();
      const tags: string[] = Array.isArray(data.tags) ? data.tags : [];
      tags.forEach(tag => {
        const entry = tagMap.get(tag) || { count: 0, sections: [] };
        entry.count++;
        entry.sections.push({
          id: doc.id,
          title: data.title || '',
          bookTitle: data.bookTitle || '',
          bookId: data.bookId || '',
        });
        tagMap.set(tag, entry);
      });
    });

    const result = Array.from(tagMap.entries())
      .map(([tag, data]) => ({ tag, count: data.count, sections: data.sections }))
      .sort((a, b) => a.tag.localeCompare(b.tag, 'he'));

    setCache(cacheKey, result, 60_000);
    return NextResponse.json(result, { headers: CACHE_HEADERS });
  } catch (error) {
    console.error('Tags GET error:', error);
    return NextResponse.json([]);
  }
}
