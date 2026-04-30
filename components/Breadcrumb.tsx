'use client';

import React from 'react';
import Link from 'next/link';
import { ChevronLeft } from 'lucide-react';

interface BreadcrumbItem {
  label: string;
  href?: string;
}

export function Breadcrumb({ items }: { items: BreadcrumbItem[] }) {
  return (
    <nav className="flex items-center gap-1.5 text-sm text-[#6B5D4F] flex-wrap font-sans">
      {items.map((item, idx) => (
        <React.Fragment key={idx}>
          {idx > 0 && <ChevronLeft size={14} className="text-[#D6C8A8]" />}
          {item.href ? (
            <Link href={item.href} className="hover:text-[#B14F1C] transition-colors">
              {item.label}
            </Link>
          ) : (
            <span className="text-[#1F1A14] font-bold tracking-wide">{item.label}</span>
          )}
        </React.Fragment>
      ))}
    </nav>
  );
}
