'use client';

import React from 'react';

export function BookLoader({ text = 'טוען...' }: { text?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-6 py-16">
      {/* Elegant loading animation */}
      <div className="relative w-20 h-20">
        {/* Outer ring - slow rotation */}
        <div className="absolute inset-0 rounded-full border-2 border-[#E5E0D8]" />
        <div
          className="absolute inset-0 rounded-full border-2 border-transparent border-t-[#8C2B2B]"
          style={{ animation: 'loaderSpin 1.2s cubic-bezier(0.5, 0, 0.5, 1) infinite' }}
        />

        {/* Inner book icon - gentle pulse */}
        <div
          className="absolute inset-0 flex items-center justify-center"
          style={{ animation: 'loaderPulse 2s ease-in-out infinite' }}
        >
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#8C2B2B" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
            <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
          </svg>
        </div>
      </div>

      {/* Text with shimmer effect */}
      <div className="relative overflow-hidden">
        <span className="font-serif text-lg text-[#8C7A6B] tracking-wide">{text}</span>
        <div
          className="absolute inset-0"
          style={{
            background: 'linear-gradient(90deg, transparent 0%, rgba(140,43,43,0.08) 50%, transparent 100%)',
            animation: 'loaderShimmer 2s ease-in-out infinite',
          }}
        />
      </div>

      {/* Three subtle dots */}
      <div className="flex gap-1.5">
        {[0, 1, 2].map(i => (
          <div
            key={i}
            className="w-1.5 h-1.5 rounded-full bg-[#8C2B2B]"
            style={{
              animation: 'loaderDot 1.4s ease-in-out infinite',
              animationDelay: `${i * 0.2}s`,
            }}
          />
        ))}
      </div>

      <style>{`
        @keyframes loaderSpin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        @keyframes loaderPulse {
          0%, 100% { opacity: 0.6; transform: scale(0.95); }
          50% { opacity: 1; transform: scale(1.05); }
        }
        @keyframes loaderShimmer {
          0% { transform: translateX(100%); }
          100% { transform: translateX(-100%); }
        }
        @keyframes loaderDot {
          0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
          40% { opacity: 1; transform: scale(1.2); }
        }
      `}</style>
    </div>
  );
}
