'use client';

import { useEffect, useRef, useState } from 'react';
import { usePathname } from 'next/navigation';

export function NavigationProgress() {
  const pathname = usePathname();
  const [state, setState] = useState<'idle' | 'loading' | 'completing'>('idle');
  const [width, setWidth] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval>>(undefined);
  const pathnameRef = useRef(pathname);

  // Intercept link clicks to detect navigation start
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      const anchor = (e.target as HTMLElement).closest('a');
      if (!anchor) return;
      const href = anchor.getAttribute('href');
      if (!href || href === '#' || href.startsWith('http') || href.startsWith('mailto:') || href.startsWith('tel:')) return;
      if (anchor.target === '_blank') return;
      try {
        const url = new URL(href, window.location.origin);
        if (url.pathname === pathname) return;
      } catch {
        return;
      }
      // Start progress
      if (timerRef.current) clearInterval(timerRef.current);
      setState('loading');
      setWidth(30);
      timerRef.current = setInterval(() => {
        setWidth(w => w >= 90 ? 90 : w + (90 - w) * 0.08);
      }, 150);
    };
    document.addEventListener('click', handler, true);
    return () => document.removeEventListener('click', handler, true);
  }, [pathname]);

  // When pathname changes, complete the progress
  useEffect(() => {
    if (pathnameRef.current !== pathname) {
      if (timerRef.current) clearInterval(timerRef.current);
      if (state === 'loading') {
        setState('completing');
        setWidth(100);
        const t = setTimeout(() => {
          setState('idle');
          setWidth(0);
        }, 300);
        pathnameRef.current = pathname;
        return () => clearTimeout(t);
      }
      pathnameRef.current = pathname;
    }
  }, [pathname, state]);

  if (state === 'idle') return null;

  return (
    <div className="fixed top-0 left-0 right-0 z-[9999] h-[3px]">
      <div
        className="h-full bg-[#8C2B2B]"
        style={{
          width: `${width}%`,
          transition: state === 'completing' ? 'width 200ms ease-out' : 'width 300ms ease-out',
          boxShadow: '0 0 8px rgba(140,43,43,0.4)',
        }}
      />
    </div>
  );
}
