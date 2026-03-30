import { createClient } from "@/lib/supabase/server";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { statusLabels, formatDate } from "@/lib/utils";
import Link from "next/link";
import type { TaskStatus } from "@/types";

export default async function AdminDashboard() {
  const supabase = await createClient();

  const [clientsRes, tasksRes, activeSubsRes] = await Promise.all([
    supabase.from("clients").select("*, user:users(full_name, email)"),
    supabase
      .from("tasks")
      .select("*, client:clients(user:users(full_name, email))")
      .order("updated_at", { ascending: false })
      .limit(20),
    supabase
      .from("clients")
      .select("id", { count: "exact" })
      .eq("status", "active"),
  ]);

  const clients = clientsRes.data || [];
  const tasks = tasksRes.data || [];
  const activeCount = activeSubsRes.count || 0;

  const tasksByStatus = tasks.reduce(
    (acc, t) => {
      acc[t.status] = (acc[t.status] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  const statusVariant: Record<string, "info" | "warning" | "purple" | "default" | "success"> = {
    submitted: "info",
    in_progress: "warning",
    internal_review: "purple",
    client_review: "warning",
    completed: "success",
  };

  const subStatusVariant: Record<string, "success" | "error" | "warning" | "default"> = {
    active: "success",
    canceled: "error",
    past_due: "warning",
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text-primary">
          Admin Dashboard
        </h1>
        <p className="text-sm text-text-secondary mt-1">
          Overview of clients, subscriptions, and tasks.
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <p className="text-sm text-text-secondary mb-1">Total Clients</p>
          <p className="text-3xl font-bold text-text-primary">
            {clients.length}
          </p>
        </Card>
        <Card>
          <p className="text-sm text-text-secondary mb-1">
            Active Subscriptions
          </p>
          <p className="text-3xl font-bold text-text-primary">{activeCount}</p>
        </Card>
        <Card>
          <p className="text-sm text-text-secondary mb-1">Open Tasks</p>
          <p className="text-3xl font-bold text-text-primary">
            {(tasksByStatus["submitted"] || 0) +
              (tasksByStatus["in_progress"] || 0) +
              (tasksByStatus["internal_review"] || 0) +
              (tasksByStatus["client_review"] || 0)}
          </p>
        </Card>
        <Card>
          <p className="text-sm text-text-secondary mb-1">Completed</p>
          <p className="text-3xl font-bold text-text-primary">
            {tasksByStatus["completed"] || 0}
          </p>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Clients */}
        <Card>
          <CardHeader>
            <CardTitle>Clients</CardTitle>
            <Link
              href="/admin/clients"
              className="text-sm text-accent hover:text-accent-hover"
            >
              View all
            </Link>
          </CardHeader>
          <div className="space-y-3">
            {clients.slice(0, 8).map((client) => {
              const userInfo = client.user as Record<string, string> | null;
              return (
                <Link
                  key={client.id}
                  href={`/admin/clients/${client.id}`}
                  className="flex items-center justify-between p-3 rounded-lg hover:bg-surface-hover transition-colors"
                >
                  <div>
                    <p className="text-sm font-medium text-text-primary">
                      {userInfo?.full_name || userInfo?.email || "Unknown"}
                    </p>
                    <p className="text-xs text-text-tertiary">
                      Plan {client.plan || "—"}
                    </p>
                  </div>
                  <Badge variant={subStatusVariant[client.status] || "default"}>
                    {client.status}
                  </Badge>
                </Link>
              );
            })}
          </div>
        </Card>

        {/* Recent Task Timeline */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Tasks</CardTitle>
            <Link
              href="/admin/tasks"
              className="text-sm text-accent hover:text-accent-hover"
            >
              View all
            </Link>
          </CardHeader>
          <div className="space-y-3">
            {tasks.slice(0, 8).map((task) => {
              const clientUser = (
                task.client as Record<string, Record<string, string> | null> | null
              )?.user;
              return (
                <Link
                  key={task.id}
                  href={`/admin/tasks/${task.id}`}
                  className="flex items-center justify-between p-3 rounded-lg hover:bg-surface-hover transition-colors"
                >
                  <div className="min-w-0 flex-1 mr-3">
                    <p className="text-sm font-medium text-text-primary truncate">
                      {task.title}
                    </p>
                    <p className="text-xs text-text-tertiary">
                      {clientUser?.full_name || clientUser?.email || "Unknown"}{" "}
                      &middot; {formatDate(task.updated_at)}
                    </p>
                  </div>
                  <Badge variant={statusVariant[task.status] || "default"}>
                    {statusLabels[task.status as TaskStatus]}
                  </Badge>
                </Link>
              );
            })}
          </div>
        </Card>
      </div>
    </div>
  );
}
