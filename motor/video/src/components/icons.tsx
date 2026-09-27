import React from "react";
import { icons } from "lucide-react";

type IP = { size: number; color: string };

// heart inside a crosshair
const HeartTarget: React.FC<IP> = ({ size, color }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2} strokeLinecap="round">
    <circle cx="12" cy="12" r="9" fill={`${color}33`} />
    <path d="M12 1.5v3M12 19.5v3M1.5 12h3M19.5 12h3" />
    <path
      d="M12 16.2s-4.2-2.6-4.2-5.4c0-1.4 1-2.4 2.3-2.4.8 0 1.5.4 1.9 1.1.4-.7 1.1-1.1 1.9-1.1 1.3 0 2.3 1 2.3 2.4 0 2.8-4.2 5.4-4.2 5.4z"
      fill={color}
      stroke="none"
    />
  </svg>
);

// hooded figure
const Hood: React.FC<IP> = ({ size, color }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.8} strokeLinejoin="round">
    <path d="M12 2.2C7.4 2.2 4.6 6 4.6 10.6v6.1L2.8 21.8h18.4l-1.8-5.1v-6.1C19.4 6 16.6 2.2 12 2.2z" fill={`${color}40`} />
    <path d="M7.6 12.2c0-3 1.9-5.6 4.4-5.6s4.4 2.6 4.4 5.6c0 2.4-1.9 4.3-4.4 4.3s-4.4-1.9-4.4-4.3z" fill="#0b0b10" />
    <path d="M9.6 12.3l1.4.5M14.4 12.3l-1.4.5" stroke={color} strokeWidth={1.4} strokeLinecap="round" />
  </svg>
);

const CUSTOM: Record<string, React.FC<IP>> = { HeartTarget, Hood };
const LUCIDE = icons as Record<string, React.ComponentType<{ size?: number; color?: string; strokeWidth?: number; fill?: string }>>;

/** Any Lucide icon by PascalCase name (https://lucide.dev/icons), plus HeartTarget and Hood. */
export const Icon: React.FC<{ name: string; size: number; color: string }> = ({ name, size, color }) => {
  const Custom = CUSTOM[name];
  if (Custom) return <Custom size={size} color={color} />;
  const Comp = LUCIDE[name] ?? LUCIDE.Circle;
  return <Comp size={size} color={color} strokeWidth={2.1} fill={`${color}38`} />;
};
