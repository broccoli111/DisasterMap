export type UserRole = "admin" | "worker" | "client";

export type SubscriptionPlan = "A" | "B";

export type SubscriptionStatus = "active" | "canceled" | "past_due" | "trialing";

export type TaskStatus =
  | "submitted"
  | "in_progress"
  | "internal_review"
  | "client_review"
  | "completed";

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  role: UserRole;
  created_at: string;
}

export interface Client {
  id: string;
  user_id: string;
  stripe_customer_id: string | null;
  subscription_id: string | null;
  plan: SubscriptionPlan | null;
  status: SubscriptionStatus;
  created_at: string;
  user?: User;
}

export interface Task {
  id: string;
  client_id: string;
  assigned_to: string | null;
  title: string;
  description: string;
  status: TaskStatus;
  created_at: string;
  updated_at: string;
  client?: Client;
  assignee?: User;
}

export interface TaskFile {
  id: string;
  task_id: string;
  file_url: string;
  file_name: string;
  uploaded_by: string;
  file_type: "brief" | "deliverable";
  created_at: string;
  uploader?: User;
}

export interface Comment {
  id: string;
  task_id: string;
  user_id: string;
  content: string;
  created_at: string;
  user?: User;
}

export interface StatusUpdate {
  id: string;
  task_id: string;
  old_status: TaskStatus | null;
  new_status: TaskStatus;
  changed_by: string;
  created_at: string;
  user?: User;
}

export interface SiteContent {
  id: string;
  page: string;
  section: string;
  content: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface PricingTier {
  id: string;
  name: string;
  plan: SubscriptionPlan;
  price: number;
  features: string[];
  stripe_price_id: string;
  created_at: string;
}

export interface FAQ {
  id: string;
  question: string;
  answer: string;
  sort_order: number;
  created_at: string;
}
