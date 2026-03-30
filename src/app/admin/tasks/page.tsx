import { createClient } from "@/lib/supabase/server";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { statusLabels, formatDate } from "@/lib/utils";
import Link from "next/link";
import type { TaskStatus } from "@/types";

export default async function AdminTasksPage() {
  const supabase = await createClient();

  const { data: tasks } = await supabase
    .from("tasks")
    .select(
      "*, client:clients(user:users(full_name, email)), assignee:users!tasks_assigned_to_fkey(full_name, email)"
    )
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
        <h1 className="text-2xl font-bold text-text-primary">All Tasks</h1>
        <p className="text-sm text-text-secondary mt-1">
          Manage tasks across all clients.
        </p>
      </div>

      {tasks && tasks.length > 0 ? (
        <Card padding={false}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left p-4 font-medium text-text-secondary">
                    Task
                  </th>
                  <th className="text-left p-4 font-medium text-text-secondary">
                    Client
                  </th>
                  <th className="text-left p-4 font-medium text-text-secondary">
                    Assigned To
                  </th>
                  <th className="text-left p-4 font-medium text-text-secondary">
                    Status
                  </th>
                  <th className="text-left p-4 font-medium text-text-secondary">
                    Updated
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {tasks.map((task) => {
                  const clientUser = (
                    task.client as Record<
                      string,
                      Record<string, string> | null
                    > | null
                  )?.user;
                  const assignee = task.assignee as Record<
                    string,
                    string
                  > | null;
                  return (
                    <tr
                      key={task.id}
                      className="hover:bg-surface-hover transition-colors"
                    >
                      <td className="p-4">
                        <Link
                          href={`/admin/tasks/${task.id}`}
                          className="text-text-primary font-medium hover:text-accent"
                        >
                          {task.title}
                        </Link>
                      </td>
                      <td className="p-4 text-text-secondary">
                        {clientUser?.full_name || clientUser?.email || "—"}
                      </td>
                      <td className="p-4 text-text-secondary">
                        {assignee?.full_name || assignee?.email || "Unassigned"}
                      </td>
                      <td className="p-4">
                        <Badge
                          variant={statusVariant[task.status] || "default"}
                        >
                          {statusLabels[task.status as TaskStatus]}
                        </Badge>
                      </td>
                      <td className="p-4 text-text-tertiary">
                        {formatDate(task.updated_at)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      ) : (
        <EmptyState
          title="No tasks yet"
          description="Tasks submitted by clients will appear here."
        />
      )}
    </div>
  );
}
