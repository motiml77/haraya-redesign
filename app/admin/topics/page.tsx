'use client';

import React, { useState, useEffect } from 'react';
import { Hash, ChevronDown, BookOpen } from 'lucide-react';
import Link from 'next/link';
import { BookLoader } from '@/components/BookLoader';

interface TagData {
 tag: string;
 count: number;
 sections: { id: string; title: string; bookTitle: string }[];
}

export default function AdminTopicsPage() {
 const [tags, setTags] = useState<TagData[]>([]);
 const [isLoading, setIsLoading] = useState(true);
 const [expandedTag, setExpandedTag] = useState<string | null>(null);

 useEffect(() => {
 fetch('/api/tags')
 .then(r => r.json())
 .then(data => {
 if (Array.isArray(data)) setTags(data);
 setIsLoading(false);
 })
 .catch(() => setIsLoading(false));
 }, []);

 if (isLoading) return <BookLoader text="טוען נושאים..." />;

 return (
 <div className="space-y-6">
 <div className="flex justify-between items-center">
 <h1 className="text-2xl font-bold text-[#1F1A14] flex items-center gap-2">
 <Hash size={24} className="text-[#B14F1C]" />
 נושאים ({tags.length})
 </h1>
 </div>

 {tags.length === 0 ? (
 <p className="text-center text-[#6B5D4F] py-12">אין נושאים עדיין. הוסף תגיות לחלקים כדי ליצור נושאים.</p>
 ) : (
 <div className="grid grid-cols-1 gap-3">
 {tags.map(({ tag, count, sections }) => (
 <div key={tag} className="bg-[#E8DCC4] border border-[#D6C8A8] overflow-hidden">
 <button onClick={() => setExpandedTag(expandedTag === tag ? null : tag)}
 className="w-full flex justify-between items-center p-4 hover:bg-[#F1E6D2] transition-colors text-right">
 <div className="flex items-center gap-3">
 <span className="text-[#B14F1C] font-bold text-lg">#</span>
 <span className="font-bold text-[#1F1A14] text-lg">{tag}</span>
 <span className="text-xs text-[#6B5D4F] bg-[#E8DCC4] px-2 py-0.5 rounded-full">{count} חלקים</span>
 </div>
 <ChevronDown size={20} className={`text-[#6B5D4F] transition-transform ${expandedTag === tag ? 'rotate-180' : ''}`} />
 </button>

 {expandedTag === tag && (
 <div className="border-t border-[#D6C8A8] p-4 bg-[#F1E6D2] space-y-2">
 {sections.map(s => (
 <Link key={s.id} href={`/admin/sections/${s.id}`}
 className="flex items-center gap-3 p-3 bg-[#E8DCC4] border border-[#D6C8A8] hover:border-[#B14F1C] transition-colors group">
 <BookOpen size={16} className="text-[#6B5D4F] group-hover:text-[#B14F1C] shrink-0" />
 <div className="flex-1 min-w-0">
 <span className="text-sm font-bold text-[#1F1A14] block truncate">{s.title}</span>
 <span className="text-xs text-[#6B5D4F]">{s.bookTitle}</span>
 </div>
 </Link>
 ))}
 </div>
 )}
 </div>
 ))}
 </div>
 )}
 </div>
 );
}
