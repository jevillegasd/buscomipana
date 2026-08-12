// Inline SVG icon set per docs/identity/es.md section 4: outlined, 2px
// constant stroke, no external icon library or font -- each of these is well
// under the 1KB-per-icon budget since they're plain path data, not fonts.
import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

const base = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export function CheckCircleIcon(props: IconProps) {
  return (
    <svg {...base} className="w-6 h-6" {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M8.5 12.5l2.5 2.5 5-5.5" />
    </svg>
  );
}

export function AlertTriangleIcon(props: IconProps) {
  return (
    <svg {...base} className="w-6 h-6" {...props}>
      <path d="M12 3.5l9.5 16.5H2.5L12 3.5z" />
      <path d="M12 10v4" />
      <circle cx="12" cy="17.2" r="0.6" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function UsersIcon(props: IconProps) {
  return (
    <svg {...base} className="w-6 h-6" {...props}>
      <circle cx="9" cy="8.5" r="3" />
      <path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6" />
      <path d="M16 4.5c1.7.4 3 2 3 3.9 0 1.9-1.3 3.5-3 3.9" />
      <path d="M15 14c2.8.4 5 2.8 5 6" />
    </svg>
  );
}

export function HandshakeIcon(props: IconProps) {
  return (
    <svg {...base} className="w-6 h-6" {...props}>
      <path d="M2.5 11l4-3.5c.6-.5 1.5-.5 2 0l2.2 2" />
      <path d="M21.5 11l-4-3.5c-.6-.5-1.5-.5-2 0l-1 1" />
      <path d="M6.5 10.5l3.3 3.3c.6.6 1.6.6 2.2 0 .6-.6.6-1.6 0-2.2" />
      <path d="M11.8 13.8l1.2 1.2c.6.6 1.6.6 2.2 0 .6-.6.6-1.6 0-2.2" />
      <path d="M17.5 10.5l-3.8 3.8" />
      <path d="M2.5 11l2.3 6.5 3.7 1.5" />
      <path d="M21.5 11l-2.3 6.5-3.2 1.3" />
    </svg>
  );
}

export function SignalSlashIcon(props: IconProps) {
  return (
    <svg {...base} className="w-6 h-6" {...props}>
      <path d="M3 3l18 18" />
      <path d="M5 18v-3" />
      <path d="M9.5 18v-6" />
      <path d="M14 18v-2.5" />
      <path d="M18.5 18v-9.5" />
    </svg>
  );
}
