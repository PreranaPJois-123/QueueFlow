import { kindMeta } from "../lib/kinds";
import type { VenueKind } from "../types";

function hash(text: string) {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 16777619);
  return h >>> 0;
}

/** Deterministic illustrated cover: the category colour with a geometric
 * pattern seeded by the venue name. Decorative only (no photos are claimed). */
export function VenueCover({ name, kind, className = "", large = false }: {
  name: string; kind: VenueKind; className?: string; large?: boolean;
}) {
  const meta = kindMeta[kind];
  const Icon = meta.icon;
  const seed = hash(name);
  const shapes = Array.from({ length: 6 }, (_, i) => {
    const v = (seed >> (i * 5)) & 31;
    return { cx: 10 + ((v * 37 + i * 53) % 90), cy: 10 + ((v * 23 + i * 41) % 80), r: 6 + (v % 18) };
  });
  return (
    <div aria-hidden className={`relative overflow-hidden ${className}`} style={{ backgroundColor: meta.solid }}>
      <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice">
        {shapes.map((s, i) => (
          <circle key={i} cx={s.cx} cy={s.cy} r={s.r} fill="white" fillOpacity={0.05 + (i % 3) * 0.04} />
        ))}
        <path d={`M0 ${70 + (seed % 15)} Q 50 ${45 + (seed % 25)} 100 ${60 + (seed % 20)} V100 H0 Z`} fill="black" fillOpacity="0.12" />
      </svg>
      <div className={`absolute ${large ? "bottom-6 right-6" : "bottom-3 right-3"} flex items-center justify-center rounded-xl bg-white/15 backdrop-blur-sm ${large ? "h-16 w-16" : "h-10 w-10"}`}>
        <Icon className={`${large ? "h-8 w-8" : "h-5 w-5"} text-white`} strokeWidth={1.75} />
      </div>
      <span className={`font-display absolute left-4 top-3 font-bold text-white/25 ${large ? "text-7xl" : "text-5xl"}`}>
        {name.replace(/[^A-Za-z]/g, "").slice(0, 2)}
      </span>
    </div>
  );
}
