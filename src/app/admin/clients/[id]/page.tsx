import { createClient } from "@/lib/supabase/server";
import { notFound } from "next/navigation";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { statusLabels, formatDate } from "@/lib/utils";
import Link from "next/link";
import type { TaskStatus } from "@/types";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function AdminClientDetailPage({ params }: Props) {
  const { id } = await params;
  const supabase = await createClient();

  const { data: client } = await supabase
    .from("clients")
    .select("*, user:users(full_name, email)")
    .eq("id", id)
    .single();

  if (!client) notFound();

  const { data: tasks } = await supabase
    .from("tasks")
    .select("*")
    .eq("client_id", id)
    .order("created_at", { ascending: false });

  const userInfo = client.user as Record<string, string> | null;

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

  const activeTasks = (tasks || []).filter((t) => t.status !== "completed");
  const completedTasks = (tasks || []).filter(
    (t) => t.status === "completed"
  );

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/admin/clients"
          className="text-sm text-text-secondary hover:text-text-primary mb-2 inline-block"
        >
          &larr; Back to Clients
        </Link>
        <h1 className="text-2xl font-bold text-text-primary">
          {userInfo?.full_name || userInfo?.email || "Client"}
        </h1>
      </div>

      {/* Client info */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <p className="text-sm text-text-secondary mb-1">Email</p>
          <p className="text-sm font-medium text-text-primary">
            {userInfo?.email}
          </p>
        </Card>
        <Card>
          <p className="text-sm text-text-secondary mb-1">Plan</p>
          <p className="text-sm font-medium text-text-primary">
            {client.plan ? `Plan ${client.plan}` : "No plan"}
          </p>
        </Card>
        <Card>
          <p className="text-sm text-text-secondary mb-1">Subscription</p>
          <Badge variant={subStatusVariant[client.status] || "default"}>
            {client.status}
          </Badge>
        </Card>
        <Card>
          <p className="text-sm text-text-secondary mb-1">Total Tasks</p>
          <p className="text-sm font-medium text-text-primary">
            {(tasks || []).length}
          </p>
        </Card>
      </div>

      {/* Active tasks */}
      <Card>
        <CardHeader>
          <CardTitle>Active Tasks ({activeTasks.length})</CardTitle>
        </CardHeader>
        {activeTasks.length > 0 ? (
          <div className="space-y-3">
            {activeTasks.map((task) => (
              <Link
                key={task.id}
                href={`/admin/tasks/${task.id}`}
                className="flex items-center justify-between p-3 rounded-lg hover:bg-surface-hover transition-colors"
              >
                <div>
                  <p className="text-sm font-medium text-text-primary">
                    {task.title}
                  </p>
                  <p className="text-xs text-text-tertiary">
                    {formatDate(task.created_at)}
                  </p>
                </div>
                <Badge variant={statusVariant[task.status] || "default"}>
                  {statusLabels[task.status as TaskStatus]}
                </Badge>
              </Link>
            ))}
          </div>
        ) : (
          <p className="text-sm text-text-secondary">No active tasks.</p>
        )}
      </Card>

      {/* Completed tasks */}
      <Card>
        <CardHeader>
          <CardTitle>Completed Tasks ({completedTasks.length})</CardTitle>
        </CardHeader>
        {completedTasks.length > 0 ? (
          <div className="space-y-3">
            {completedTasks.map((task) => (
              <Link
                key={task.id}
                href={`/admin/tasks/${task.id}`}
                className="flex items-center justify-between p-3 rounded-lg hover:bg-surface-hover transition-colors"
              >
                <div>
                  <p className="text-sm font-medium text-text-primary">
                    {task.title}
                  </p>
                  <p className="text-xs text-text-tertiary">
                    Completed {formatDate(task.updated_at)}
                  </p>
                </div>
                <Badge variant="success">Completed</Badge>
              </Link>
            ))}
          </div>
        ) : (
          <p className="text-sm text-text-secondary">
            No completed tasks yet.
          </p>
        )}
      </Card>
    </div>
  );
}
