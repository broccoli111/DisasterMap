"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { useState } from "react";

export function MarketingNav() {
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border bg-surface/80 backdrop-blur-md">
      <div className="max-w-6xl mx-auto flex h-16 items-center justify-between px-5 sm:px-6">
        <Link href="/" className="flex items-center gap-2">
          <div className="w-7 h-7 bg-accent rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">S</span>
          </div>
          <span className="font-semibold text-text-primary">SaaS Platform</span>
        </Link>

        <nav className="hidden md:flex items-center gap-8">
          <a
            href="#pricing"
            className="text-sm text-text-secondary hover:text-text-primary transition-colors"
          >
            Pricing
          </a>
          <a
            href="#faq"
            className="text-sm text-text-secondary hover:text-text-primary transition-colors"
          >
            FAQ
          </a>
        </nav>

        <div className="hidden md:flex items-center gap-3">
          <Link href="/login">
            <Button variant="ghost" size="sm">
              Log in
            </Button>
          </Link>
          <Link href="/signup">
            <Button size="sm">Get Started</Button>
          </Link>
        </div>

        {/* Mobile hamburger */}
        <button
          className="md:hidden p-2 -mr-2 text-text-secondary hover:text-text-primary"
          onClick={() => setOpen(!open)}
          aria-label="Toggle menu"
        >
          {open ? (
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          ) : (
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 9h16.5m-16.5 6.75h16.5" />
            </svg>
          )}
        </button>
      </div>

      {/* Mobile menu */}
      {open && (
        <div className="md:hidden border-t border-border bg-surface">
          <nav className="flex flex-col px-5 py-4 space-y-1">
            <a
              href="#pricing"
              onClick={() => setOpen(false)}
              className="text-sm text-text-secondary hover:text-text-primary py-2.5 transition-colors"
            >
              Pricing
            </a>
            <a
              href="#faq"
              onClick={() => setOpen(false)}
              className="text-sm text-text-secondary hover:text-text-primary py-2.5 transition-colors"
            >
              FAQ
            </a>
            <div className="pt-3 border-t border-border flex flex-col gap-2">
              <Link href="/login" onClick={() => setOpen(false)}>
                <Button variant="outline" className="w-full">
                  Log in
                </Button>
              </Link>
              <Link href="/signup" onClick={() => setOpen(false)}>
                <Button className="w-full">Get Started</Button>
              </Link>
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}
