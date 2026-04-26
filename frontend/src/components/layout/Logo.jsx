import React from 'react';

export default function Logo({ size = 'md' }) {
  const sizes = {
    sm: { box: 'w-7 h-7', text: 'text-sm', sub: 'text-[10px]' },
    md: { box: 'w-8 h-8', text: 'text-base', sub: 'text-xs' },
    lg: { box: 'w-10 h-10', text: 'text-lg', sub: 'text-sm' },
  };
  const s = sizes[size];

  return (
    <div className="flex items-center gap-2.5">
      <div className={`${s.box} rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center`}>
        <span className="text-primary font-bold text-lg">S</span>
      </div>
      <div className="flex flex-col">
        <span className={`${s.text} font-semibold text-foreground tracking-tight leading-none`}>
          Sąmatų AI
        </span>
        <span className={`${s.sub} text-muted-foreground leading-none mt-0.5`}>
          Sąmatų platforma
        </span>
      </div>
    </div>
  );
}