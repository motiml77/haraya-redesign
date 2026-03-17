// Client-side sessionStorage cache for instant page loads
// Uses stale-while-revalidate pattern: show cached data immediately, fetch fresh in background

export function getCachedData<T = any>(url: string): T | null {
  try {
    const cached = sessionStorage.getItem(`cache:${url}`);
    if (cached) {
      const { data, expires } = JSON.parse(cached);
      if (Date.now() < expires) return data as T;
    }
  } catch {}
  return null;
}

export function setCachedData(url: string, data: any, ttlSeconds: number = 300) {
  try {
    sessionStorage.setItem(`cache:${url}`, JSON.stringify({
      data,
      expires: Date.now() + ttlSeconds * 1000,
    }));
  } catch {}
}
