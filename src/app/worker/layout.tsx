import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";
import { DashboardIcon, TasksIcon } from "@/components/icons";

const workerNav = [
  { label: "Dashboard", href: "/worker", icon: <DashboardIcon /> },
  { label: "My Tasks", href: "/worker/tasks", icon: <TasksIcon /> },
];

export default async function WorkerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login?redirect=/worker");

  const { data: profile } = await supabase
    .from("users")
    .select("*")
    .eq("id", user.id)
    .single();

  if (!profile || profile.role !== "worker") redirect("/portal");

  return (
    <div className="min-h-screen bg-surface-secondary">
      <Sidebar items={workerNav} title="Worker" subtitle="Dashboard" />
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
