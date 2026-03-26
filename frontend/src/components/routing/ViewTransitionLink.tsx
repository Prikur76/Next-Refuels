"use client";

import Link, { type LinkProps } from "next/link";
import { useRouter } from "next/navigation";
import type { AnchorHTMLAttributes, ReactNode } from "react";

function supportsViewTransition(): boolean {
  if (typeof document === "undefined") return false;
  return "startViewTransition" in document;
}

function hrefToString(href: LinkProps["href"]): string {
  if (typeof href === "string") return href;
  if (typeof href === "object" && href.pathname) return href.pathname;
  return "/";
}

export function ViewTransitionLink({
  href,
  children,
  onClick,
  ...rest
}: LinkProps &
  Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href" | "onClick"> & {
    children: ReactNode;
  }) {
  const router = useRouter();

  return (
    <Link
      href={href}
      {...rest}
      onClick={(e) => {
        onClick?.(e);
        if (e.defaultPrevented) return;
        if (!supportsViewTransition()) return;

        const destination = hrefToString(href);
        e.preventDefault();
        // View Transitions API: smooth cross-route animations.
        document.startViewTransition(() => router.push(destination));
      }}
    >
      {children}
    </Link>
  );
}

