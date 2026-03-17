'use client';

import React, { useState, useEffect, useRef } from 'react';
import { X } from 'lucide-react';

interface TagInputProps {
  tags: string[];
  onChange: (tags: string[]) => void;
}

export function TagInput({ tags, onChange }: TagInputProps) {
  const [inputValue, setInputValue] = useState('');
  const [allTags, setAllTags] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [filteredSuggestions, setFilteredSuggestions] = useState<string[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Fetch all existing tags once
  useEffect(() => {
    fetch('/api/tags')
      .then(r => r.json())
      .then((data: any[]) => {
        if (Array.isArray(data)) {
          setAllTags(data.map(d => d.tag).sort((a, b) => a.localeCompare(b, 'he')));
        }
      })
      .catch(() => {});
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setInputValue(val);

    // Filter suggestions - show when typing # or any text
    const search = val.startsWith('#') ? val.slice(1) : val;
    if (val.startsWith('#') || search.length > 0) {
      const filtered = allTags
        .filter(t => !tags.includes(t) && t.includes(search))
        .sort((a, b) => a.localeCompare(b, 'he'));
      setFilteredSuggestions(filtered);
      setShowSuggestions(true);
    } else {
      setShowSuggestions(false);
    }
  };

  const addTag = (tag: string) => {
    const cleaned = tag.replace(/^#/, '').trim();
    if (cleaned && !tags.includes(cleaned)) {
      onChange([...tags, cleaned]);
    }
    setInputValue('');
    setShowSuggestions(false);
    inputRef.current?.focus();
  };

  const removeTag = (tag: string) => {
    onChange(tags.filter(t => t !== tag));
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      if (inputValue.trim()) {
        addTag(inputValue);
      }
    } else if (e.key === 'Backspace' && !inputValue && tags.length > 0) {
      removeTag(tags[tags.length - 1]);
    }
  };

  const showAllSuggestions = () => {
    const filtered = allTags
      .filter(t => !tags.includes(t))
      .sort((a, b) => a.localeCompare(b, 'he'));
    setFilteredSuggestions(filtered);
    setShowSuggestions(true);
  };

  return (
    <div ref={containerRef} className="relative">
      <div className="flex flex-wrap gap-2 p-3 rounded-xl border border-[#E5E0D8] bg-[#FAF8F5] focus-within:ring-2 focus-within:ring-[#8C2B2B] min-h-[48px] items-center cursor-text"
        onClick={() => inputRef.current?.focus()}>
        {tags.map(tag => (
          <span key={tag} className="flex items-center gap-1 px-2.5 py-1 bg-[#F0EBE1] text-[#4A3B32] text-sm rounded-full border border-[#E5E0D8]">
            <span className="text-[#8C2B2B] font-bold">#</span>{tag}
            <button onClick={(e) => { e.stopPropagation(); removeTag(tag); }}
              className="text-[#8C7A6B] hover:text-red-500 transition-colors">
              <X size={14} />
            </button>
          </span>
        ))}
        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onFocus={showAllSuggestions}
          className="flex-1 min-w-[120px] bg-transparent outline-none text-sm"
          placeholder={tags.length === 0 ? 'הקלד # כדי להוסיף נושא...' : 'הוסף נושא...'}
        />
      </div>

      {/* Suggestions dropdown */}
      {showSuggestions && filteredSuggestions.length > 0 && (
        <div className="absolute z-50 w-full mt-1 bg-white rounded-xl border border-[#E5E0D8] shadow-lg max-h-48 overflow-y-auto custom-scrollbar">
          {filteredSuggestions.map(tag => (
            <button key={tag} onClick={() => addTag(tag)}
              className="w-full text-right px-4 py-2 text-sm hover:bg-[#FAF8F5] transition-colors flex items-center gap-2 border-b border-[#F0EBE1] last:border-0">
              <span className="text-[#8C2B2B] font-bold">#</span>
              <span className="text-[#4A3B32]">{tag}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
