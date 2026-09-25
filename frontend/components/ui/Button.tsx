import type { ButtonHTMLAttributes } from "react";

export type ButtonVariant = "primary" | "secondary" | "danger" | "gold" | "ghost" | "outline";

const VARIANTS: Record<ButtonVariant, string> = {
  primary: "bg-primary border-primary-dark text-white",
  secondary: "bg-secondary border-secondary-dark text-white",
  danger: "bg-danger border-danger-dark text-white",
  gold: "bg-gold border-gold-dark text-white",
  outline: "bg-white border-2 border-b-4 border-line text-secondary",
  ghost: "border-transparent bg-transparent text-muted hover:bg-surface",
};

const DISABLED = "disabled:bg-locked disabled:border-locked-dark disabled:text-muted";

export function buttonClasses(variant: ButtonVariant = "primary", extra = ""): string {
  return `btn-chunky ${VARIANTS[variant]} ${variant === "ghost" ? "" : DISABLED} ${extra}`;
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  fullWidth?: boolean;
}

export function Button({
  variant = "primary",
  fullWidth = false,
  className = "",
  type = "button",
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={buttonClasses(variant, `${fullWidth ? "w-full" : ""} ${className}`)}
      {...props}
    />
  );
}
