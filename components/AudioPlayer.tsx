'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Play, Pause } from 'lucide-react';

interface AudioPlayerProps {
  src: string;
}

const SPEEDS = [1, 1.25, 1.5, 2];

export function AudioPlayer({ src }: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [speed, setSpeed] = useState(1);

  useEffect(() => {
    const audio = new Audio(src);
    audioRef.current = audio;

    audio.addEventListener('loadedmetadata', () => setDuration(audio.duration));
    audio.addEventListener('timeupdate', () => setCurrentTime(audio.currentTime));
    audio.addEventListener('ended', () => { setIsPlaying(false); setCurrentTime(0); });

    return () => {
      audio.pause();
      audio.src = '';
    };
  }, [src]);

  const togglePlay = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (isPlaying) {
      audio.pause();
    } else {
      audio.play();
    }
    setIsPlaying(!isPlaying);
  }, [isPlaying]);

  const cycleSpeed = useCallback(() => {
    const nextIndex = (SPEEDS.indexOf(speed) + 1) % SPEEDS.length;
    const newSpeed = SPEEDS[nextIndex];
    setSpeed(newSpeed);
    if (audioRef.current) audioRef.current.playbackRate = newSpeed;
  }, [speed]);

  const handleSeek = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const audio = audioRef.current;
    if (!audio || !duration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    // RTL: clicking left = end of track, clicking right = start
    const clickX = e.clientX - rect.left;
    const ratio = clickX / rect.width;
    // In RTL the visual direction is reversed, so we use 1-ratio
    audio.currentTime = (1 - ratio) * duration;
  }, [duration]);

  const formatTime = (s: number) => {
    if (!s || !isFinite(s)) return '0:00';
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className="flex items-center gap-1.5 px-1.5 py-1 bg-[#E8DCC4]" dir="rtl">
      <button onClick={togglePlay}
        className="shrink-0 w-6 h-6 flex items-center justify-center bg-[#B14F1C] text-white rounded-full hover:bg-[#7A2525] transition-colors">
        {isPlaying ? <Pause size={10} /> : <Play size={10} className="mr-[-1px]" />}
      </button>
      <div className="flex-1 flex items-center gap-1.5 min-w-0">
        <span className="text-[9px] text-[#6B5D4F] font-mono shrink-0">{formatTime(currentTime)}</span>
        <div className="flex-1 h-1 bg-[#D6C8A8] rounded-full cursor-pointer relative" onClick={handleSeek}>
          <div className="absolute top-0 right-0 h-full bg-[#B14F1C] rounded-full transition-all"
            style={{ width: `${progress}%` }} />
        </div>
        <span className="text-[9px] text-[#6B5D4F] font-mono shrink-0">{formatTime(duration)}</span>
      </div>
      <button onClick={cycleSpeed}
        className="shrink-0 px-1 py-0 text-[9px] font-bold text-[#B14F1C] bg-[#E8DCC4] border border-[#D6C8A8] hover:bg-[#E8DCC4] transition-colors leading-4">
        {speed}x
      </button>
    </div>
  );
}
