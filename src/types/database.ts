import type {
  UserRole,
  SubscriptionPlan,
  SubscriptionStatus,
  TaskStatus,
} from "./index";

export interface Database {
  public: {
    Tables: {
      users: {
        Row: {
          id: string;
          email: string;
          full_name: string | null;
          role: UserRole;
          created_at: string;
        };
        Insert: {
          id: string;
          email: string;
          full_name?: string | null;
          role?: UserRole;
          created_at?: string;
        };
        Update: {
          id?: string;
          email?: string;
          full_name?: string | null;
          role?: UserRole;
          created_at?: string;
        };
      };
      clients: {
        Row: {
          id: string;
          user_id: string;
          stripe_customer_id: string | null;
          subscription_id: string | null;
          plan: SubscriptionPlan | null;
          status: SubscriptionStatus;
          created_at: string;
        };
        Insert: {
          id?: string;
          user_id: string;
          stripe_customer_id?: string | null;
          subscription_id?: string | null;
          plan?: SubscriptionPlan | null;
          status?: SubscriptionStatus;
          created_at?: string;
        };
        Update: {
          id?: string;
          user_id?: string;
          stripe_customer_id?: string | null;
          subscription_id?: string | null;
          plan?: SubscriptionPlan | null;
          status?: SubscriptionStatus;
          created_at?: string;
        };
      };
      tasks: {
        Row: {
          id: string;
          client_id: string;
          assigned_to: string | null;
          title: string;
          description: string;
          status: TaskStatus;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          client_id: string;
          assigned_to?: string | null;
          title: string;
          description: string;
          status?: TaskStatus;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          id?: string;
          client_id?: string;
          assigned_to?: string | null;
          title?: string;
          description?: string;
          status?: TaskStatus;
          created_at?: string;
          updated_at?: string;
        };
      };
      task_files: {
        Row: {
          id: string;
          task_id: string;
          file_url: string;
          file_name: string;
          uploaded_by: string;
          file_type: "brief" | "deliverable";
          created_at: string;
        };
        Insert: {
          id?: string;
          task_id: string;
          file_url: string;
          file_name: string;
          uploaded_by: string;
          file_type: "brief" | "deliverable";
          created_at?: string;
        };
        Update: {
          id?: string;
          task_id?: string;
          file_url?: string;
          file_name?: string;
          uploaded_by?: string;
          file_type?: "brief" | "deliverable";
          created_at?: string;
        };
      };
      comments: {
        Row: {
          id: string;
          task_id: string;
          user_id: string;
          content: string;
          created_at: string;
        };
        Insert: {
          id?: string;
          task_id: string;
          user_id: string;
          content: string;
          created_at?: string;
        };
        Update: {
          id?: string;
          task_id?: string;
          user_id?: string;
          content?: string;
          created_at?: string;
        };
      };
      status_updates: {
        Row: {
          id: string;
          task_id: string;
          old_status: TaskStatus | null;
          new_status: TaskStatus;
          changed_by: string;
          created_at: string;
        };
        Insert: {
          id?: string;
          task_id: string;
          old_status?: TaskStatus | null;
          new_status: TaskStatus;
          changed_by: string;
          created_at?: string;
        };
        Update: {
          id?: string;
          task_id?: string;
          old_status?: TaskStatus | null;
          new_status?: TaskStatus;
          changed_by?: string;
          created_at?: string;
        };
      };
      site_content: {
        Row: {
          id: string;
          page: string;
          section: string;
          content: Record<string, unknown>;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          page: string;
          section: string;
          content: Record<string, unknown>;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          id?: string;
          page?: string;
          section?: string;
          content?: Record<string, unknown>;
          created_at?: string;
          updated_at?: string;
        };
      };
      pricing_tiers: {
        Row: {
          id: string;
          name: string;
          plan: SubscriptionPlan;
          price: number;
          features: string[];
          stripe_price_id: string;
          created_at: string;
        };
        Insert: {
          id?: string;
          name: string;
          plan: SubscriptionPlan;
          price: number;
          features: string[];
          stripe_price_id: string;
          created_at?: string;
        };
        Update: {
          id?: string;
          name?: string;
          plan?: SubscriptionPlan;
          price?: number;
          features?: string[];
          stripe_price_id?: string;
          created_at?: string;
        };
      };
      faqs: {
        Row: {
          id: string;
          question: string;
          answer: string;
          sort_order: number;
          created_at: string;
        };
        Insert: {
          id?: string;
          question: string;
          answer: string;
          sort_order?: number;
          created_at?: string;
        };
        Update: {
          id?: string;
          question?: string;
          answer?: string;
          sort_order?: number;
          created_at?: string;
        };
      };
    };
  };
}
