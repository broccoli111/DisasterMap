"use client";

import { createClient } from "@/lib/supabase/client";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Card } from "@/components/ui/card";
import { statusLabels } from "@/lib/utils";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { TaskStatus } from "@/types";

interface AdminTaskControlsProps {
  taskId: string;
  userId: string;
  currentStatus: TaskStatus;
  currentAssignee: string | null;
  workers: { id: string; label: string }[];
}

const allStatuses: TaskStatus[] = [
  "submitted",
  "in_progress",
  "internal_review",
  "client_review",
  "completed",
];

export function AdminTaskControls({
  taskId,
  userId,
  currentStatus,
  currentAssignee,
  workers,
}: AdminTaskControlsProps) {
  const [assignee, setAssignee] = useState(currentAssignee || "");
  const [status, setStatus] = useState<TaskStatus>(currentStatus);
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const supabase = createClient();

  async function handleSave() {
    setLoading(true);

    const updates: Record<string, unknown> = {};
    if (assignee !== (currentAssignee || "")) {
      updates.assigned_to = assignee || null;
    }
    if (status !== currentStatus) {
      updates.status = status;
    }

    if (Object.keys(updates).length > 0) {
      await supabase.from("tasks").update(updates).eq("id", taskId);

      if (status !== currentStatus) {
        await supabase.from("status_updates").insert({
          task_id: taskId,
          old_status: currentStatus,
          new_status: status,
          changed_by: userId,
        });
      }
    }

    setLoading(false);
    router.refresh();
  }

  return (
    <Card>
      <p className="text-sm font-medium text-text-primary mb-4">
        Task Controls
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Select
          label="Assign Worker"
          value={assignee}
          onChange={(e) => setAssignee(e.target.value)}
          options={[
            { value: "", label: "Unassigned" },
            ...workers.map((w) => ({ value: w.id, label: w.label })),
          ]}
        />
        <Select
          label="Status"
          value={status}
          onChange={(e) => setStatus(e.target.value as TaskStatus)}
          options={allStatuses.map((s) => ({
            value: s,
            label: statusLabels[s],
          }))}
        />
      </div>
      <div className="mt-4">
        <Button onClick={handleSave} loading={loading} size="sm">
          Save Changes
        </Button>
      </div>
    </Card>
  );
}
