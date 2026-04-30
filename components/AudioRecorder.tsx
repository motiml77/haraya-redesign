'use client';

import React, { useState, useRef, useCallback } from 'react';
import { Mic, Square, Trash2, Loader2, Pause, Play, Upload } from 'lucide-react';
import { storage, auth } from '@/lib/firebase';

interface AudioRecorderProps {
  sectionId: string;
  commentId: string | number;
  authorName: string;
  onRecorded: (audioUrl: string) => void;
  onClear: () => void;
  audioUrl: string | null;
}

const MAX_SECONDS = 300; // 5 minutes

// Detect best supported audio format
function getAudioConfig(): { mimeType: string; ext: string } {
  if (typeof MediaRecorder === 'undefined') return { mimeType: '', ext: 'webm' };
  if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) return { mimeType: 'audio/webm;codecs=opus', ext: 'webm' };
  if (MediaRecorder.isTypeSupported('audio/webm')) return { mimeType: 'audio/webm', ext: 'webm' };
  if (MediaRecorder.isTypeSupported('audio/mp4')) return { mimeType: 'audio/mp4', ext: 'm4a' };
  if (MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')) return { mimeType: 'audio/ogg;codecs=opus', ext: 'ogg' };
  return { mimeType: '', ext: 'webm' };
}

export function AudioRecorder({ sectionId, commentId, authorName, onRecorded, onClear, audioUrl }: AudioRecorderProps) {
  const [status, setStatus] = useState<'idle' | 'recording' | 'paused' | 'preview' | 'uploading'>('idle');
  const [seconds, setSeconds] = useState(0);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const previewBlobRef = useRef<Blob | null>(null);
  const secondsRef = useRef(0);
  const audioConfigRef = useRef<{ mimeType: string; ext: string }>({ mimeType: '', ext: 'webm' });

  const startRecording = useCallback(async () => {
    if (typeof MediaRecorder === 'undefined') {
      alert('הדפדפן אינו תומך בהקלטה. נסה דפדפן אחר.');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const config = getAudioConfig();
      audioConfigRef.current = config;

      const recorderOptions: MediaRecorderOptions = {};
      if (config.mimeType) recorderOptions.mimeType = config.mimeType;

      const mediaRecorder = new MediaRecorder(stream, recorderOptions);
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = () => {
        stream.getTracks().forEach(t => t.stop());
        streamRef.current = null;

        const blobType = config.mimeType || mediaRecorder.mimeType || 'audio/webm';
        const blob = new Blob(chunksRef.current, { type: blobType });
        if (blob.size === 0) {
          setStatus('idle');
          return;
        }

        previewBlobRef.current = blob;
        const url = URL.createObjectURL(blob);
        setPreviewUrl(url);
        setStatus('preview');
      };

      mediaRecorder.start(1000);
      setSeconds(0);
      secondsRef.current = 0;
      setStatus('recording');

      timerRef.current = setInterval(() => {
        secondsRef.current += 1;
        setSeconds(secondsRef.current);
        if (secondsRef.current >= MAX_SECONDS) {
          if (timerRef.current) {
            clearInterval(timerRef.current);
            timerRef.current = null;
          }
          if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
            mediaRecorderRef.current.stop();
          }
        }
      }, 1000);
    } catch (err) {
      console.error('Mic access error:', err);
      alert('לא ניתן לגשת למיקרופון. יש לאשר גישה בדפדפן.');
    }
  }, []);

  const pauseRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.pause();
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      setStatus('paused');
    }
  }, []);

  const resumeRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'paused') {
      mediaRecorderRef.current.resume();
      timerRef.current = setInterval(() => {
        secondsRef.current += 1;
        setSeconds(secondsRef.current);
        if (secondsRef.current >= MAX_SECONDS) {
          if (timerRef.current) {
            clearInterval(timerRef.current);
            timerRef.current = null;
          }
          if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
            mediaRecorderRef.current.stop();
          }
        }
      }, 1000);
      setStatus('recording');
    }
  }, []);

  const stopRecording = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
  }, []);

  const discardRecording = useCallback(() => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    previewBlobRef.current = null;
    setSeconds(0);
    setStatus('idle');
  }, [previewUrl]);

  const handleClear = useCallback(() => {
    onClear();
    setSeconds(0);
  }, [onClear]);

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  // Upload via REST API directly (Firebase SDK hangs on mobile)
  const handleUpload = async () => {
    const blob = previewBlobRef.current;
    if (!blob) {
      alert('לא נמצאה הקלטה להעלאה');
      return;
    }

    if (!auth.currentUser) {
      alert('יש להתחבר מחדש. רענן את הדף.');
      return;
    }

    setStatus('uploading');

    try {
      const token = await auth.currentUser.getIdToken();
      const bucket = storage.app.options.storageBucket;
      const safeName = authorName.replace(/[^a-zA-Z0-9\u0590-\u05FF]/g, '-');
      const ext = audioConfigRef.current.ext || 'webm';
      const contentType = audioConfigRef.current.mimeType || blob.type || 'audio/webm';
      const path = `audio-replies/${sectionId}/reply_${commentId}_${safeName}_${Date.now()}.${ext}`;

      const res = await fetch(
        `https://firebasestorage.googleapis.com/v0/b/${bucket}/o/${encodeURIComponent(path)}?uploadType=media`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': contentType,
          },
          body: blob,
        }
      );

      if (!res.ok) {
        throw new Error(`Upload failed: ${res.status}`);
      }

      const data = await res.json();
      const downloadUrl = `https://firebasestorage.googleapis.com/v0/b/${bucket}/o/${encodeURIComponent(data.name)}?alt=media&token=${data.downloadTokens}`;

      if (previewUrl) URL.revokeObjectURL(previewUrl);
      setPreviewUrl(null);
      previewBlobRef.current = null;

      onRecorded(downloadUrl);
      setStatus('idle');
    } catch (err: any) {
      console.error('Upload error:', err);
      alert(`שגיאה בהעלאה: ${err?.message || 'שגיאה לא ידועה'}`);
      setStatus('preview');
    }
  };

  // Show playback if already uploaded & saved
  if (audioUrl) {
    return (
      <div className="flex items-center gap-2 p-2 bg-[#E8DCC4]">
        <audio src={audioUrl} controls className="h-8 flex-1" style={{ minWidth: 0 }} />
        <button onClick={handleClear} className="p-1.5 text-red-500 hover:bg-red-50 transition-colors" title="מחק הקלטה">
          <Trash2 size={16} />
        </button>
      </div>
    );
  }

  if (status === 'uploading') {
    return (
      <div className="flex items-center gap-2 p-2 bg-[#E8DCC4] text-sm text-[#6B5D4F]">
        <Loader2 size={16} className="animate-spin" />
        <span>מעלה הקלטה...</span>
      </div>
    );
  }

  if (status === 'preview' && previewUrl) {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2 p-2 bg-[#E8DCC4]">
          <audio src={previewUrl} controls className="h-8 flex-1" style={{ minWidth: 0 }} />
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleUpload}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-white bg-[#B14F1C] hover:bg-[#7A2525] transition-colors"
            title="אשר והעלה">
            <Upload size={14} />
            <span>אשר והעלה</span>
          </button>
          <button onClick={discardRecording}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-red-600 border border-red-300 hover:bg-red-50 transition-colors"
            title="מחק והקלט מחדש">
            <Trash2 size={14} />
            <span>מחק</span>
          </button>
        </div>
      </div>
    );
  }

  if (status === 'recording' || status === 'paused') {
    return (
      <div className="flex items-center gap-2 p-2 bg-red-50 border border-red-200">
        <div className={`w-2.5 h-2.5 bg-red-500 rounded-full ${status === 'recording' ? 'animate-pulse' : 'opacity-50'}`} />
        <span className="text-sm text-red-700 font-mono">{formatTime(seconds)}</span>
        <span className="text-xs text-red-500">{status === 'recording' ? 'מקליט...' : 'מושהה'}</span>
        <span className="text-[10px] text-red-400">({formatTime(MAX_SECONDS - seconds)} נותרו)</span>
        <div className="mr-auto flex items-center gap-1.5">
          {status === 'recording' ? (
            <button onClick={pauseRecording}
              className="p-1.5 bg-yellow-500 text-white hover:bg-yellow-600 transition-colors" title="השהה">
              <Pause size={14} />
            </button>
          ) : (
            <button onClick={resumeRecording}
              className="p-1.5 bg-green-500 text-white hover:bg-green-600 transition-colors" title="המשך">
              <Play size={14} />
            </button>
          )}
          <button onClick={stopRecording}
            className="flex items-center gap-1.5 px-2.5 py-1.5 bg-red-500 text-white hover:bg-red-600 transition-colors text-xs font-bold" title="סיים הקלטה">
            <Square size={12} />
            <span>סיים הקלטה</span>
          </button>
        </div>
      </div>
    );
  }

  return (
    <button onClick={startRecording}
      className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-[#B14F1C] border border-[#B14F1C]/30 hover:bg-[#B14F1C]/5 transition-colors"
      title="הקלט תשובה קולית">
      <Mic size={14} />
      <span>הקלט תשובה</span>
    </button>
  );
}
