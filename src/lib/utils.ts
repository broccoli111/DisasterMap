import { type TaskStatus } from "@/types";

export function cn(...classes: (string | boolean | undefined | null)[]): string {
  return classes.filter(Boolean).join(" ");
}

export function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function formatDateTime(dateString: string): string {
  return new Date(dateString).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
  }).format(amount);
}

export const statusLabels: Record<TaskStatus, string> = {
  submitted: "Submitted",
  in_progress: "In Progress",
  internal_review: "Internal Review",
  client_review: "Client Review",
  completed: "Completed",
};

export const statusColors: Record<TaskStatus, string> = {
  submitted: "bg-blue-100 text-blue-800",
  in_progress: "bg-yellow-100 text-yellow-800",
  internal_review: "bg-purple-100 text-purple-800",
  client_review: "bg-orange-100 text-orange-800",
  completed: "bg-green-100 text-green-800",
};
