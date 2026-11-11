import React from "react";

/* ── iOS 风格基础组件 ── */

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`ios-card p-4 ${className}`}>{children}</div>;
}

export function SectionTitle({ children }: { children: React.ReactNode }) {
  return <div className="ios-section-title">{children}</div>;
}

export function BigTitle({ children, sub }: { children: React.ReactNode; sub?: string }) {
  return (
    <div className="px-1 pb-3 pt-1">
      <div className="text-[28px] font-bold leading-tight">{children}</div>
      {sub && <div className="text-[13px] text-ios-label2 mt-0.5">{sub}</div>}
    </div>
  );
}

export function Switch({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={`relative w-[51px] h-[31px] rounded-full transition-colors duration-200 ease-ios
        ${checked ? "bg-[#30D158]" : "bg-black/15 dark:bg-white/20"}`}
      aria-pressed={checked}
    >
      <span className={`absolute top-[2px] left-[2px] w-[27px] h-[27px] bg-white rounded-full
        shadow-md transition-transform duration-200 ease-ios ${checked ? "translate-x-[20px]" : ""}`} />
    </button>
  );
}

export function Modal({ title, children, onClose, wide }: {
  title: string; children: React.ReactNode; onClose: () => void; wide?: boolean;
}) {
  return (
    <div className="fixed inset-0 z-50 bg-black/45 flex items-center justify-center animate-[fade_.15s_ease-ios]"
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className={`bg-white dark:bg-[#1C1C1E] rounded-[16px] shadow-float p-6 ${wide ? "w-[720px] max-w-[92vw]" : "w-[420px] max-w-[90vw]"}
        max-h-[80vh] overflow-auto animate-[pop_.2s_ease-ios]`}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[16px] font-bold">{title}</h3>
          <button className="text-ios-label2 hover:text-current text-[18px] px-2" onClick={onClose}>✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Segmented<T extends string>({ value, options, onChange }: {
  value: T; options: { value: T; label: string }[]; onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex bg-black/5 dark:bg-white/10 rounded-[9px] p-[2px]">
      {options.map(o => (
        <button key={o.value} onClick={() => onChange(o.value)}
          className={`px-3 py-1 text-[13px] rounded-[7px] font-medium transition-all duration-200 ease-ios
          ${value === o.value ? "bg-white dark:bg-[#3A3A3C] shadow-sm" : "text-ios-label2"}`}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function StatCard({ value, label, tone = "blue" }: { value: React.ReactNode; label: string; tone?: string }) {
  const tones: Record<string, string> = {
    blue: "text-[#0A84FF]", green: "text-[#30D158]", red: "text-[#FF453A]",
    orange: "text-[#FF9500]", neutral: "",
  };
  return (
    <Card className="min-w-0">
      <div className={`text-[26px] font-bold leading-none ${tones[tone] || ""}`}>{value}</div>
      <div className="text-[12px] text-ios-label2 mt-1.5">{label}</div>
    </Card>
  );
}

export function Spinner({ text }: { text?: string }) {
  return (
    <div className="flex items-center gap-2 text-ios-label2 text-[13px]">
      <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
      {text}
    </div>
  );
}
