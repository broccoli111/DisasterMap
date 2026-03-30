import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { statusLabels, formatDate } from "@/lib/utils";
import Link from "next/link";
import type { TaskStatus } from "@/types";

export default async function WorkerTasksPage() {
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
        <h1 className="text-2xl font-bold text-text-primary">My Tasks</h1>
        <p className="text-sm text-text-secondary mt-1">
          All tasks assigned to you.
        </p>
      </div>

      {tasks && tasks.length > 0 ? (
        <Card padding={false}>
          <div className="divide-y divide-border">
            {tasks.map((task) => {
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
                  className="flex items-center justify-between p-4 hover:bg-surface-hover transition-colors"
                >
                  <div className="min-w-0 flex-1 mr-3">
                    <p className="text-sm font-medium text-text-primary truncate">
                      {task.title}
                    </p>
                    <p className="text-xs text-text-tertiary mt-0.5">
                      {clientUser?.full_name || clientUser?.email || "Unknown"}{" "}
                      &middot; {formatDate(task.created_at)}
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
      ) : (
        <EmptyState
          title="No assigned tasks"
          description="Tasks assigned to you by an admin will appear here."
        />
      )}
    </div>
  );
}
