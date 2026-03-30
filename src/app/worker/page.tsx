import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { statusLabels, formatDate } from "@/lib/utils";
import Link from "next/link";
import type { TaskStatus } from "@/types";

export default async function WorkerDashboard() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: tasks } = await supabase
    .from("tasks")
    .select("*, client:clients(user:users(full_name, email))")
    .eq("assigned_to", user.id)
    .order("updated_at", { ascending: false });

  const activeTasks = (tasks || []).filter((t) => t.status !== "completed");
  const completedTasks = (tasks || []).filter(
    (t) => t.status === "completed"
  );

  const statusVariant: Record<string, "info" | "warning" | "purple" | "default" | "success"> = {
    submitted: "info",
    in_progress: "warning",
    internal_review: "purple",
    client_review: "warning",
    completed: "success",
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text-primary">
          Worker Dashboard
        </h1>
        <p className="text-sm text-text-secondary mt-1">
          Your assigned tasks and progress.
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <p className="text-sm text-text-secondary mb-1">Assigned Tasks</p>
          <p className="text-3xl font-bold text-text-primary">
            {(tasks || []).length}
          </p>
        </Card>
        <Card>
          <p className="text-sm text-text-secondary mb-1">Active</p>
          <p className="text-3xl font-bold text-text-primary">
            {activeTasks.length}
          </p>
        </Card>
        <Card>
          <p className="text-sm text-text-secondary mb-1">Completed</p>
          <p className="text-3xl font-bold text-text-primary">
            {completedTasks.length}
          </p>
        </Card>
      </div>

      {/* Active tasks */}
      <Card>
        <CardHeader>
          <CardTitle>Active Tasks</CardTitle>
        </CardHeader>
        {activeTasks.length > 0 ? (
          <div className="space-y-3">
            {activeTasks.map((task) => {
              const clientUser = (
                task.client as Record<
                  string,
                  Record<string, string> | null
                > | null
              )?.user;
              return (
                <Link
                  key={task.id}
                  href={`/worker/tasks/${task.id}`}
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
        ) : (
          <p className="text-sm text-text-secondary">
            No active tasks assigned.
          </p>
        )}
      </Card>
    </div>
  );
}
