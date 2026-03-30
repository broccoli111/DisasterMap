"use client";

import { createClient } from "@/lib/supabase/client";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

interface TopbarProps {
  user: {
    email: string;
    full_name?: string | null;
    role: string;
  };
}

export function Topbar({ user }: TopbarProps) {
  const router = useRouter();
  const supabase = createClient();

  async function handleSignOut() {
    await supabase.auth.signOut();
    router.push("/login");
    router.refresh();
  }

  return (
    <header className="h-16 border-b border-border bg-surface flex items-center justify-between px-6 sticky top-0 z-20">
      <div />
      <div className="flex items-center gap-4">
        <div className="text-right">
          <p className="text-sm font-medium text-text-primary">
            {user.full_name || user.email}
          </p>
          <p className="text-xs text-text-tertiary capitalize">{user.role}</p>
        </div>
        <div className="w-8 h-8 rounded-full bg-accent flex items-center justify-center">
          <span className="text-white text-xs font-semibold">
            {(user.full_name || user.email)[0].toUpperCase()}
          </span>
        </div>
        <Button variant="ghost" size="sm" onClick={handleSignOut}>
          Sign out
        </Button>
      </div>
    </header>
  );
}
