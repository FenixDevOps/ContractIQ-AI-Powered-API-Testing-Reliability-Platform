import { forwardRef } from "react";
import { cva } from "class-variance-authority";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-canvas disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-[#dce4f1] text-[#13161b] hover:bg-white",
        secondary: "border border-line bg-panel text-[#e2e5eb] hover:bg-[#20242c]",
        ghost: "text-[#a6abb5] hover:bg-[#20242c] hover:text-white",
        outline: "border border-line bg-transparent text-[#c2c6ce] hover:bg-[#1d2128]",
      },
      size: {
        default: "h-9 px-3.5",
        sm: "h-8 px-3 text-xs",
        icon: "size-9 p-0",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export const Button = forwardRef(function Button(
  { className, variant, size, type = "button", ...props },
  ref,
) {
  return (
    <button
      className={cn(buttonVariants({ variant, size }), className)}
      ref={ref}
      type={type}
      {...props}
    />
  );
});
