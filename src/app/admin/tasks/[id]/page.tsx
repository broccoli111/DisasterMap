import { createClient } from "@/lib/supabase/server";
import { redirect, notFound } from "next/navigation";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { statusLabels, formatDate, formatDateTime } from "@/lib/utils";
import { TaskComments } from "@/components/task-comments";
import { TaskActions } from "@/components/task-actions";
import { AdminTaskControls } from "@/components/admin-task-controls";
import type { TaskStatus } from "@/types";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function AdminTaskDetailPage({ params }: Props) {
  const { id } = await params;
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: task } = await supabase
    .from("tasks")
    .select(
      "*, client:clients(user:users(full_name, email)), assignee:users!tasks_assigned_to_fkey(full_name, email)"
    )
    .eq("id", id)
    .single();

  if (!task) notFound();

  // Get all workers for assignment
  const { data: workers } = await supabase
    .from("users")
    .select("id, full_name, email")
    .eq("role", "worker");

  const { data: files } = await supabase
    .from("task_files")
    .select("*, uploader:users(full_name, email)")
    .eq("task_id", id)
    .order("created_at");

  const { data: statusUpdates } = await supabase
    .from("status_updates")
    .select("*, user:users(full_name, email)")
    .eq("task_id", id)
    .order("created_at");

  const { data: comments } = await supabase
    .from("comments")
    .select("*, user:users(full_name, email)")
    .eq("task_id", id)
    .order("created_at");

  const clientUser = (
    task.client as Record<string, Record<string, string> | null> | null
  )?.user;
  const assignee = task.assignee as Record<string, string> | null;

  const statusVariant: Record<string, "info" | "warning" | "purple" | "default" | "success"> = {
    submitted: "info",
    in_progress: "warning",
    internal_review: "purple",
    client_review: "warning",
    completed: "success",
  };

  const briefFiles = (files || []).filter((f) => f.file_type === "brief");
  const deliverableFiles = (files || []).filter(
    (f) => f.file_type === "deliverable"
  );

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <a
            href="/admin/tasks"
            className="text-sm text-text-secondary hover:text-text-primary mb-2 inline-block"
          >
            &larr; Back to Tasks
          </a>
          <h1 className="text-2xl font-bold text-text-primary">{task.title}</h1>
          <p className="text-sm text-text-secondary mt-1">
            Client: {clientUser?.full_name || clientUser?.email || "Unknown"}{" "}
            &middot; Created {formatDate(task.created_at)}
          </p>
        </div>
        <Badge
          variant={statusVariant[task.status] || "default"}
          className="text-sm"
        >
          {statusLabels[task.status as TaskStatus]}
        </Badge>
      </div>

      {/* Admin controls: assign worker, change status */}
      <AdminTaskControls
        taskId={task.id}
        userId={user.id}
        currentStatus={task.status as TaskStatus}
        currentAssignee={task.assigned_to}
        workers={(workers || []).map((w) => ({
          id: w.id,
          label: w.full_name || w.email,
        }))}
      />

      {/* Review actions */}
      <TaskActions
        taskId={task.id}
        userId={user.id}
        role="admin"
        currentStatus={task.status as TaskStatus}
      />

      {/* Description */}
      <Card>
        <CardHeader>
          <CardTitle>Description</CardTitle>
        </CardHeader>
        <p className="text-sm text-text-secondary whitespace-pre-wrap">
          {task.description}
        </p>
      </Card>

      {/* Current assignment */}
      <Card>
        <CardHeader>
          <CardTitle>Assignment</CardTitle>
        </CardHeader>
        <p className="text-sm text-text-secondary">
          Assigned to:{" "}
          <span className="font-medium text-text-primary">
            {assignee?.full_name || assignee?.email || "Unassigned"}
          </span>
        </p>
      </Card>

      {/* Brief files */}
      {briefFiles.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Brief Attachments</CardTitle>
          </CardHeader>
          <div className="space-y-2">
            {briefFiles.map((file) => (
              <a
                key={file.id}
                href={file.file_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 p-3 rounded-lg border border-border hover:bg-surface-hover transition-colors"
              >
                <svg className="w-5 h-5 text-text-tertiary flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                </svg>
                <span className="text-sm text-text-primary truncate">
                  {file.file_name}
                </span>
              </a>
            ))}
          </div>
        </Card>
      )}

      {/* Deliverables */}
      {deliverableFiles.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Deliverables</CardTitle>
          </CardHeader>
          <div className="space-y-2">
            {deliverableFiles.map((file) => (
              <a
                key={file.id}
                href={file.file_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 p-3 rounded-lg border border-border hover:bg-surface-hover transition-colors"
              >
                <svg className="w-5 h-5 text-accent flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                </svg>
                <span className="text-sm text-text-primary truncate">
                  {file.file_name}
                </span>
              </a>
            ))}
          </div>
        </Card>
      )}

      {/* Timeline */}
      <Card>
        <CardHeader>
          <CardTitle>Timeline</CardTitle>
        </CardHeader>
        <div className="space-y-4">
          {(statusUpdates || []).map((update) => {
            const userName =
              (update.user as Record<string, string> | null)?.full_name ||
              (update.user as Record<string, string> | null)?.email ||
              "System";
            return (
              <div key={update.id} className="flex gap-3">
                <div className="w-2 h-2 rounded-full bg-accent mt-2 flex-shrink-0" />
                <div>
                  <p className="text-sm text-text-primary">
                    <span className="font-medium">{userName}</span>
                    {update.old_status
                      ? ` changed status from ${
                          statusLabels[update.old_status as TaskStatus]
                        } to ${statusLabels[update.new_status as TaskStatus]}`
                      : ` created the task`}
                  </p>
                  <p className="text-xs text-text-tertiary">
                    {formatDateTime(update.created_at)}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      {/* Comments */}
      <Card>
        <CardHeader>
          <CardTitle>Comments</CardTitle>
        </CardHeader>
        <TaskComments
          taskId={task.id}
          userId={user.id}
          initialComments={(comments || []).map((c) => ({
            id: c.id,
            content: c.content,
            created_at: c.created_at,
            userName:
              (c.user as Record<string, string> | null)?.full_name ||
              (c.user as Record<string, string> | null)?.email ||
              "Unknown",
          }))}
        />
      </Card>
    </div>
  );
}
