'use client';

import React, { useState } from 'react';
import Image from 'next/image';
import { ChevronDown, ChevronUp, Plus, Play, X, Loader2 } from 'lucide-react';
import { YouTubeVideo } from '@/lib/types';
import { authFetch } from '@/lib/auth-fetch';

const extractVideoId = (url: string): string | null => {
  const patterns = [
    /(?:youtube\.com\/watch\?v=)([a-zA-Z0-9_-]{11})/,
    /(?:youtu\.be\/)([a-zA-Z0-9_-]{11})/,
    /(?:youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})/,
    /(?:youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})/,
  ];
  for (const p of patterns) {
    const m = url.match(p);
    if (m) return m[1];
  }
  return null;
};

const getThumbnail = (videoId: string) => `https://img.youtube.com/vi/${videoId}/mqdefault.jpg`;

async function fetchYouTubeTitle(videoId: string): Promise<string | null> {
  try {
    const res = await fetch(
      `https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=${videoId}&format=json`
    );
    if (res.ok) {
      const data = await res.json();
      return data.title || null;
    }
  } catch { }
  return null;
}

interface YouTubePlaylistProps {
  sectionId: string;
  videos: YouTubeVideo[];
  canEdit: boolean;
  onUpdate: (videos: YouTubeVideo[]) => void;
}

export function YouTubePlaylist({ sectionId, videos, canEdit, onUpdate }: YouTubePlaylistProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [activeVideoId, setActiveVideoId] = useState<string | null>(videos[0]?.videoId || null);
  const [newUrl, setNewUrl] = useState('');
  const [newTitle, setNewTitle] = useState('');
  const [error, setError] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  // Hide entirely if no videos and not editor
  if (videos.length === 0 && !canEdit) return null;

  const saveVideos = async (updated: YouTubeVideo[]): Promise<boolean> => {
    setIsSaving(true);
    setError('');
    try {
      const res = await authFetch(`/api/sections/${sectionId}`, {
        method: 'PUT',
        body: JSON.stringify({ youtubeVideos: updated }),
      });
      if (!res.ok) {
        const text = await res.text();
        console.error('YouTube save failed:', res.status, text);
        setError(`שגיאה בשמירה (${res.status})`);
        setIsSaving(false);
        return false;
      }
      const data = await res.json();
      if (data.success) {
        onUpdate(updated);
        setIsSaving(false);
        return true;
      } else {
        console.error('YouTube save error:', data.error);
        setError(data.error || 'שגיאה בשמירה');
        setIsSaving(false);
        return false;
      }
    } catch (err) {
      console.error('YouTube save exception:', err);
      setError('שגיאה בשמירה — בדוק שאתה מחובר');
      setIsSaving(false);
      return false;
    }
  };

  const addVideo = async () => {
    setError('');
    const vid = extractVideoId(newUrl.trim());
    if (!vid) {
      setError('קישור לא תקין — הדבק קישור YouTube');
      return;
    }
    if (videos.some(v => v.videoId === vid)) {
      setError('הסרטון כבר קיים ברשימה');
      return;
    }

    setIsSaving(true);

    // If user didn't provide a title, fetch from YouTube
    let title = newTitle.trim();
    if (!title) {
      const ytTitle = await fetchYouTubeTitle(vid);
      title = ytTitle || `שיעור ${videos.length + 1}`;
    }

    const updated = [...videos, { id: `yt_${Date.now()}`, videoId: vid, title, addedAt: Date.now() }];
    const success = await saveVideos(updated);
    if (success) {
      if (!activeVideoId) setActiveVideoId(vid);
      setNewUrl('');
      setNewTitle('');
    }
  };

  const removeVideo = async (videoId: string) => {
    const updated = videos.filter(v => v.videoId !== videoId);
    const success = await saveVideos(updated);
    if (success && activeVideoId === videoId) {
      setActiveVideoId(updated[0]?.videoId || null);
    }
  };

  const moveVideo = async (index: number, dir: number) => {
    const newIndex = index + dir;
    if (newIndex < 0 || newIndex >= videos.length) return;
    const updated = [...videos];
    [updated[index], updated[newIndex]] = [updated[newIndex], updated[index]];
    await saveVideos(updated);
  };

  const activeIndex = videos.findIndex(v => v.videoId === activeVideoId);

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-[#E5E0D8] overflow-hidden">
      {/* Header — always visible */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-[#FAF8F5] transition-colors"
      >
        <div className="flex items-center gap-3">
          <Image src="/youtube-icon.svg" alt="YouTube" width={28} height={20} className="shrink-0" />
          <span className="text-lg font-bold text-[#4A3B32]">שיעורים בנושא</span>
          {videos.length > 0 && (
            <span className="bg-[#F0EBE1] text-[#8C7A6B] text-xs font-bold px-2.5 py-0.5 rounded-full">
              {videos.length}
            </span>
          )}
        </div>
        {isOpen ? <ChevronUp size={20} className="text-[#8C7A6B]" /> : <ChevronDown size={20} className="text-[#8C7A6B]" />}
      </button>

      {/* Content — collapsible */}
      {isOpen && (
        <div className="border-t border-[#E5E0D8]">
          {/* Admin: Add video form */}
          {canEdit && (
            <div className="bg-[#FAF8F5] px-5 py-4 border-b border-[#E5E0D8]">
              <div className="text-sm font-bold text-[#8C7A6B] mb-3">הוספת שיעור</div>
              <div className="flex flex-col sm:flex-row gap-2">
                <input
                  value={newUrl}
                  onChange={(e) => { setNewUrl(e.target.value); setError(''); }}
                  placeholder="הדבק קישור YouTube..."
                  className="flex-[2] min-w-0 p-2.5 rounded-xl border border-[#E5E0D8] bg-white focus:ring-2 focus:ring-[#8C2B2B] outline-none text-sm"
                  dir="ltr"
                />
                <input
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="שם השיעור (אופציונלי — ייקח מיוטיוב)"
                  className="flex-1 min-w-0 p-2.5 rounded-xl border border-[#E5E0D8] bg-white focus:ring-2 focus:ring-[#8C2B2B] outline-none text-sm"
                />
                <button
                  onClick={addVideo}
                  disabled={isSaving}
                  className="flex items-center justify-center gap-1.5 px-4 py-2.5 bg-[#8C2B2B] text-white rounded-xl text-sm font-bold hover:bg-[#7A2525] disabled:opacity-50 transition-colors whitespace-nowrap"
                >
                  {isSaving ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
                  {isSaving ? 'שומר...' : 'הוסף'}
                </button>
              </div>
              {error && <div className="text-red-500 text-xs mt-2">{error}</div>}
            </div>
          )}

          {videos.length > 0 ? (
            <div className="flex flex-col lg:flex-row">
              {/* Player */}
              <div className="lg:flex-[3] min-w-0 p-4">
                {activeVideoId ? (
                  <>
                    <div className="relative w-full pb-[56.25%] rounded-xl overflow-hidden bg-black">
                      <iframe
                        key={activeVideoId}
                        src={`https://www.youtube.com/embed/${activeVideoId}?rel=0`}
                        className="absolute inset-0 w-full h-full"
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                        allowFullScreen
                      />
                    </div>
                    <div className="mt-3 px-1">
                      <h4 className="text-base font-bold text-[#4A3B32]">
                        {videos.find(v => v.videoId === activeVideoId)?.title}
                      </h4>
                      <div className="text-xs text-[#8C7A6B] mt-1">
                        שיעור {activeIndex + 1} מתוך {videos.length}
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="bg-[#FAF8F5] rounded-xl p-8 text-center text-[#8C7A6B] text-sm">
                    בחר שיעור מהרשימה
                  </div>
                )}
              </div>

              {/* Playlist sidebar */}
              <div className="lg:flex-[2] lg:border-r border-t lg:border-t-0 border-[#E5E0D8] max-h-[350px] overflow-y-auto">
                <div className="sticky top-0 bg-white px-4 py-3 border-b border-[#E5E0D8] z-10">
                  <div className="text-sm font-bold text-[#4A3B32]">רשימת שיעורים</div>
                </div>
                {videos.map((video, i) => {
                  const isActive = video.videoId === activeVideoId;
                  return (
                    <div
                      key={video.id}
                      onClick={() => setActiveVideoId(video.videoId)}
                      className={`flex items-center gap-2 px-3 py-2 cursor-pointer transition-colors border-b border-[#F0EBE1] last:border-b-0 ${
                        isActive ? 'bg-[#F0EBE1] border-r-[3px] border-r-[#8C2B2B]' : 'hover:bg-[#FAF8F5]'
                      }`}
                    >
                      {/* Index / play icon */}
                      <div className="w-5 text-center text-xs text-[#8C7A6B] shrink-0">
                        {isActive ? <Play size={14} className="text-[#8C2B2B]" fill="#8C2B2B" /> : i + 1}
                      </div>

                      {/* Thumbnail */}
                      <div className="w-[70px] h-[39px] rounded-md overflow-hidden shrink-0 bg-black">
                        <img
                          src={getThumbnail(video.videoId)}
                          alt=""
                          className="w-full h-full object-cover"
                        />
                      </div>

                      {/* Title */}
                      <div className="flex-1 min-w-0">
                        <div className={`text-xs leading-snug line-clamp-2 ${isActive ? 'font-bold text-[#4A3B32]' : 'text-[#6B5A4E]'}`}>
                          {video.title}
                        </div>
                      </div>

                      {/* Admin controls */}
                      {canEdit && (
                        <div className="flex flex-col gap-0.5 shrink-0" onClick={e => e.stopPropagation()}>
                          <button
                            onClick={() => moveVideo(i, -1)}
                            disabled={i === 0 || isSaving}
                            className="text-[#8C7A6B] hover:text-[#8C2B2B] disabled:opacity-30 text-xs p-0.5"
                          >
                            ▲
                          </button>
                          <button
                            onClick={() => removeVideo(video.videoId)}
                            disabled={isSaving}
                            className="text-[#8C7A6B] hover:text-red-600 disabled:opacity-30 p-0.5"
                          >
                            <X size={14} />
                          </button>
                          <button
                            onClick={() => moveVideo(i, 1)}
                            disabled={i === videos.length - 1 || isSaving}
                            className="text-[#8C7A6B] hover:text-[#8C2B2B] disabled:opacity-30 text-xs p-0.5"
                          >
                            ▼
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="px-5 py-8 text-center text-[#8C7A6B] text-sm">
              אין שיעורים עדיין. {canEdit ? 'הוסף שיעור דרך הטופס למעלה.' : ''}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
