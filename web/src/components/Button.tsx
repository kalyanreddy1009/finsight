import type { ButtonHTMLAttributes } from "react";

export type ButtonVariant = "primary" | "secondary" | "plain";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
}

// One primary (filled) button per view. Press feedback is CSS :active (scale 0.97, 100ms).
export function Button({ variant = "secondary", className, type = "button", ...rest }: ButtonProps) {
  const classes = ["btn", `btn-${variant}`, className].filter(Boolean).join(" ");
  return <button type={type} className={classes} {...rest} />;
}
