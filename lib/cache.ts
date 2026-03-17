// Server-side in-memory TTL cache for Firestore query results
// Avoids hitting Firestore on every request for data that rarely changes

const cache = new Map<string, { data: any; expires: number }>();

export function getCached<T>(key: string): T | null {
  const entry = cache.get(key);
  if (!entry) return null;
  if (Date.now() > entry.expires) {
    cache.delete(key);
    return null;
  }
  return entry.data as T;
}

export function setCache(key: string, data: any, ttlMs: number = 60_000) {
  cache.set(key, { data, expires: Date.now() + ttlMs });
}

export function invalidateCache(prefix: string) {
  for (const key of cache.keys()) {
    if (key.startsWith(prefix)) cache.delete(key);
  }
}
