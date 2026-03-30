import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";
import {
  DashboardIcon,
  UsersIcon,
  TasksIcon,
} from "@/components/icons";

const adminNav = [
  { label: "Dashboard", href: "/admin", icon: <DashboardIcon /> },
  { label: "Clients", href: "/admin/clients", icon: <UsersIcon /> },
  { label: "All Tasks", href: "/admin/tasks", icon: <TasksIcon /> },
];

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login?redirect=/admin");

  const { data: profile } = await supabase
    .from("users")
    .select("*")
    .eq("id", user.id)
    .single();

  if (!profile || profile.role !== "admin") redirect("/portal");

  return (
    <div className="min-h-screen bg-surface-secondary">
      <Sidebar items={adminNav} title="Admin" subtitle="Dashboard" />
      <div className="ml-64">
        <Topbar
          user={{
            email: profile.email,
            full_name: profile.full_name,
            role: profile.role,
          }}
        />
        <main className="p-6">{children}</main>
      </div>
    </div>
  );
}
