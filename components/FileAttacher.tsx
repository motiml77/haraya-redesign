'use client';

import React, { useState, useRef } from 'react';
import { Paperclip, Image, Camera, X, FileText, File, Loader2 } from 'lucide-react';
import { storage, auth } from '@/lib/firebase';
import type { ReplyAttachment } from '@/lib/types';

interface FileAttacherProps {
  sectionId: string;
  commentId: string | number;
  authorName: string;
  attachments: ReplyAttachment[];
  onAttachmentsChange: (attachments: ReplyAttachment[]) => void;
}

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB
const MAX_FILES = 5;

function getFileType(file: File): 'pdf' | 'docx' | 'image' | null {
  if (file.type.startsWith('image/')) return 'image';
  if (file.type === 'application/pdf') return 'pdf';
  if (file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document') return 'docx';
  // Fallback by extension
  const ext = file.name.split('.').pop()?.toLowerCase();
  if (ext === 'pdf') return 'pdf';
  if (ext === 'docx') return 'docx';
  if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'heic'].includes(ext || '')) return 'image';
  return null;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function FileAttacher({ sectionId, commentId, authorName, attachments, onAttachmentsChange }: FileAttacherProps) {
  const [uploading, setUploading] = useState(false);
  const [uploadingName, setUploadingName] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);

  const uploadFile = async (file: File) => {
    const fileType = getFileType(file);
    if (!fileType) {
      alert('סוג קובץ לא נתמך. ניתן לצרף: PDF, Word, תמונות');
      return;
    }
    if (file.size > MAX_FILE_SIZE) {
      alert(`הקובץ גדול מדי (${formatSize(file.size)}). מקסימום ${formatSize(MAX_FILE_SIZE)}`);
      return;
    }
    if (attachments.length >= MAX_FILES) {
      alert(`ניתן לצרף עד ${MAX_FILES} קבצים`);
      return;
    }
    const currentUser = auth.currentUser;
    if (!currentUser) {
      alert('יש להתחבר מחדש. רענן את הדף.');
      return;
    }

    setUploading(true);
    setUploadingName(file.name);

    try {
      const token = await currentUser.getIdToken();
      const bucket = storage.app.options.storageBucket;
      const safeName = authorName.replace(/[^a-zA-Z0-9\u0590-\u05FF]/g, '-');
      const safeFileName = file.name.replace(/[^a-zA-Z0-9\u0590-\u05FF._-]/g, '-');
      const path = `reply-attachments/${sectionId}/reply_${commentId}_${safeName}_${Date.now()}_${safeFileName}`;

      const res = await fetch(
        `https://firebasestorage.googleapis.com/v0/b/${bucket}/o/${encodeURIComponent(path)}?uploadType=media`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': file.type,
          },
          body: file,
        }
      );

      if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
      const data = await res.json();
      if (!data.name || !data.downloadTokens) throw new Error('תגובה לא תקינה מהשרת');
      const downloadUrl = `https://firebasestorage.googleapis.com/v0/b/${bucket}/o/${encodeURIComponent(data.name)}?alt=media&token=${data.downloadTokens}`;

      const newAttachment: ReplyAttachment = {
        url: downloadUrl,
        name: file.name,
        type: fileType,
        size: file.size,
      };

      onAttachmentsChange([...attachments, newAttachment]);
    } catch (err: any) {
      console.error('File upload error:', err);
      alert(`שגיאה בהעלאה: ${err?.message || 'שגיאה לא ידועה'}`);
    }

    setUploading(false);
    setUploadingName('');
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    uploadFile(files[0]);
    e.target.value = '';
  };

  const removeAttachment = (index: number) => {
    onAttachmentsChange(attachments.filter((_, i) => i !== index));
  };

  const getTypeIcon = (type: string) => {
    if (type === 'pdf') return <FileText size={14} className="text-red-500" />;
    if (type === 'docx') return <File size={14} className="text-blue-500" />;
    return <Image size={14} className="text-green-500" />;
  };

  return (
    <div className="space-y-2">
      {/* Attached files */}
      {attachments.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {attachments.map((att, i) => (
            <div key={i} className="flex items-center gap-1.5 px-2 py-1 bg-[#F0EBE1] rounded-lg text-xs">
              {getTypeIcon(att.type)}
              <span className="text-[#4A3B32] font-bold max-w-[120px] truncate">{att.name}</span>
              <span className="text-[#8C7A6B]">({formatSize(att.size)})</span>
              <button onClick={() => removeAttachment(i)} className="text-[#8C7A6B] hover:text-red-500 p-0.5">
                <X size={12} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Upload buttons */}
      {uploading ? (
        <div className="flex items-center gap-2 text-xs text-[#8C7A6B]">
          <Loader2 size={14} className="animate-spin" />
          <span>מעלה: {uploadingName}</span>
        </div>
      ) : (
        <div className="flex items-center gap-1.5 flex-wrap">
          <button onClick={() => fileInputRef.current?.click()}
            className="flex items-center gap-1 px-2.5 py-1 text-xs text-[#8C2B2B] border border-[#8C2B2B]/30 rounded-lg hover:bg-[#8C2B2B]/5 transition-colors"
            title="צרף PDF או Word">
            <Paperclip size={13} />
            <span>צרף קובץ</span>
          </button>
          <button onClick={() => imageInputRef.current?.click()}
            className="flex items-center gap-1 px-2.5 py-1 text-xs text-[#8C2B2B] border border-[#8C2B2B]/30 rounded-lg hover:bg-[#8C2B2B]/5 transition-colors"
            title="צרף תמונה מהגלריה">
            <Image size={13} />
            <span>תמונה</span>
          </button>
          <button onClick={() => cameraInputRef.current?.click()}
            className="flex items-center gap-1 px-2.5 py-1 text-xs text-[#8C2B2B] border border-[#8C2B2B]/30 rounded-lg hover:bg-[#8C2B2B]/5 transition-colors"
            title="צלם תמונה מהמצלמה">
            <Camera size={13} />
            <span>צלם</span>
          </button>

          <input ref={fileInputRef} type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={handleFileSelect} className="hidden" />
          <input ref={imageInputRef} type="file" accept="image/*" onChange={handleFileSelect} className="hidden" />
          <input ref={cameraInputRef} type="file" accept="image/*" capture="environment" onChange={handleFileSelect} className="hidden" />
        </div>
      )}
    </div>
  );
}
