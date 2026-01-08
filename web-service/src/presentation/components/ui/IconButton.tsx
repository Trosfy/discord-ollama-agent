/**
 * IconButton Component
 * 
 * A reusable icon button with consistent styling (same as send message button).
 * Supports configurable sizes: xs, sm, md, lg (default).
 */

"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

type IconButtonSize = "xs" | "sm" | "md" | "lg";

interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** Size variant: xs (20px), sm (24px), md (32px), lg (40px - default) */
  size?: IconButtonSize;
  /** Whether the button is in active/enabled state */
  active?: boolean;
  children: React.ReactNode;
}

const sizeConfig: Record<IconButtonSize, { button: string; icon: string; strokeWidth: number }> = {
  xs: {
    button: "!h-5 !w-5 !min-h-0 !min-w-0 rounded-md",
    icon: "!h-2.5 !w-2.5",
    strokeWidth: 3,
  },
  sm: {
    button: "!h-6 !w-6 !min-h-0 !min-w-0 rounded-lg",
    icon: "!h-3 !w-3",
    strokeWidth: 2.5,
  },
  md: {
    button: "!h-8 !w-8 !min-h-0 !min-w-0 rounded-lg",
    icon: "!h-4 !w-4",
    strokeWidth: 2,
  },
  lg: {
    button: "!h-10 !w-10 !min-h-0 !min-w-0 rounded-xl",
    icon: "!h-5 !w-5",
    strokeWidth: 2,
  },
};

export function IconButton({
  size = "lg",
  active = true,
  className,
  children,
  ...props
}: IconButtonProps) {
  const config = sizeConfig[size];

  return (
    <button
      type="button"
      className={cn(
        "inline-flex items-center justify-center shrink-0 transition-all",
        config.button,
        active
          ? "bg-primary hover:bg-primary/90 text-primary-foreground"
          : "bg-muted hover:bg-muted text-muted-foreground",
        props.disabled && "opacity-50 pointer-events-none",
        className
      )}
      {...props}
    >
      {React.Children.map(children, (child) => {
        if (React.isValidElement(child)) {
          return React.cloneElement(child as React.ReactElement<{ className?: string; strokeWidth?: number }>, {
            className: cn(config.icon, (child.props as { className?: string }).className),
            strokeWidth: config.strokeWidth,
          });
        }
        return child;
      })}
    </button>
  );
}

export { sizeConfig as iconButtonSizes };
export type { IconButtonSize };
