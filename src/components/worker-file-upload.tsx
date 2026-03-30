"use client";

import { createClient } from "@/lib/supabase/client";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { useRouter } from "next/navigation";
import { useState } from "react";

interface WorkerFileUploadProps {
  taskId: string;
  userId: string;
}

export function WorkerFileUpload({ taskId, userId }: WorkerFileUploadProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const router = useRouter();
  const supabase = createClient();

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (files.length === 0) return;

    setLoading(true);
    setMessage("");

    try {
      for (const file of files) {
        const path = `${taskId}/${Date.now()}-${file.name}`;
        const { error: uploadError } = await supabase.storage
          .from("deliverables")
          .upload(path, file);

        if (uploadError) {
          console.error("Upload error:", uploadError);
          continue;
        }

        const {
          data: { publicUrl },
        } = supabase.storage.from("deliverables").getPublicUrl(path);

        await supabase.from("task_files").insert({
          task_id: taskId,
          file_url: publicUrl,
          file_name: file.name,
          uploaded_by: userId,
          file_type: "deliverable",
        });
      }

      setFiles([]);
      setMessage("Files uploaded successfully.");
      router.refresh();
    } catch {
      setMessage("Failed to upload files.");
    }

    setLoading(false);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Upload Work Files</CardTitle>
      </CardHeader>
      <form onSubmit={handleUpload} className="space-y-4">
        <div className="border-2 border-dashed border-border rounded-lg p-6 text-center hover:border-border-hover transition-colors">
          <input
            type="file"
            multiple
            onChange={(e) => setFiles(Array.from(e.target.files || []))}
            className="hidden"
            id="worker-upload"
          />
          <label
            htmlFor="worker-upload"
            className="cursor-pointer text-sm text-text-secondary"
          >
            <span className="text-accent font-medium">Click to upload</span>{" "}
            deliverable files
          </label>
          {files.length > 0 && (
            <div className="mt-3 space-y-1">
              {files.map((f, i) => (
                <p key={i} className="text-xs text-text-tertiary">
                  {f.name}
                </p>
              ))}
            </div>
          )}
        </div>

        {message && (
          <p className="text-sm text-text-secondary">{message}</p>
        )}

        <Button type="submit" loading={loading} disabled={files.length === 0}>
          Upload Files
        </Button>
      </form>
    </Card>
  );
}
