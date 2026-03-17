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
    <nav className="flex items-center gap-1 text-sm text-[#8C7A6B] flex-wrap">
      {items.map((item, idx) => (
        <React.Fragment key={idx}>
          {idx > 0 && <ChevronLeft size={14} className="text-[#D5D0C8]" />}
          {item.href ? (
            <Link href={item.href} className="hover:text-[#8C2B2B] transition-colors">
              {item.label}
            </Link>
          ) : (
            <span className="text-[#4A3B32] font-bold">{item.label}</span>
          )}
        </React.Fragment>
      ))}
    </nav>
  );
}
