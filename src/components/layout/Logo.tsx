/**
 * Logo — VanillaDB wordmark with icon.
 *
 * Clean, minimal design that works at any scale.
 */

import { memo } from "react";

interface LogoProps {
  variant?: "full" | "icon";
  size?: "sm" | "md" | "lg";
}

export const Logo = memo(function Logo({
  variant = "full",
  size = "md",
}: LogoProps) {
  const iconSize = size === "sm" ? 20 : size === "md" ? 24 : 32;
  const textSize = size === "sm" ? "text-sm" : size === "md" ? "text-base" : "text-lg";
  const gap = size === "sm" ? "gap-1.5" : size === "md" ? "gap-2" : "gap-3";

  return (
    <div className={`flex items-center ${gap}`}>
      {/* Icon */}
      <div className="relative">
        <svg
          width={iconSize}
          height={iconSize}
          viewBox="0 0 32 32"
          fill="none"
          className="text-stone-700"
        >
          {/* Network nodes */}
          <circle cx="16" cy="8" r="2.5" fill="currentColor" />
          <circle cx="8" cy="20" r="2.5" fill="currentColor" />
          <circle cx="24" cy="20" r="2.5" fill="currentColor" />

          {/* Connection lines */}
          <line x1="16" y1="10.5" x2="8" y2="17.5" stroke="currentColor" strokeWidth="1.5" />
          <line x1="16" y1="10.5" x2="24" y2="17.5" stroke="currentColor" strokeWidth="1.5" />
          <line x1="8" y1="22.5" x2="24" y2="22.5" stroke="currentColor" strokeWidth="1.5" />

          {/* Center accent dot */}
          <circle cx="16" cy="16" r="1.5" fill="currentColor" opacity="0.6" />
        </svg>
      </div>

      {/* Text */}
      {variant === "full" && (
        <div className={`font-medium tracking-tight ${textSize} text-stone-900`}>
          VanillaDB
        </div>
      )}
    </div>
  );
});
