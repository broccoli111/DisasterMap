import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import Link from "next/link";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { BillingPortalButton } from "@/components/billing-portal-button";

export default async function BillingPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: client } = await supabase
    .from("clients")
    .select("*")
    .eq("user_id", user.id)
    .single();

  const statusVariant: Record<string, "success" | "error" | "warning" | "default"> = {
    active: "success",
    canceled: "error",
    past_due: "warning",
  };

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Billing</h1>
        <p className="text-sm text-text-secondary mt-1">
          Manage your subscription and billing details.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Current Plan</CardTitle>
        </CardHeader>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-lg font-bold text-text-primary">
                {client?.plan ? `Plan ${client.plan}` : "No active plan"}
              </p>
              <p className="text-sm text-text-secondary">
                {client?.plan === "A"
                  ? "$3,500/month"
                  : client?.plan === "B"
                  ? "$5,500/month"
                  : "Subscribe to get started"}
              </p>
            </div>
            <Badge variant={statusVariant[client?.status || ""] || "default"}>
              {client?.status || "inactive"}
            </Badge>
          </div>

          {client?.stripe_customer_id ? (
            <BillingPortalButton />
          ) : (
            <p className="text-sm text-text-tertiary">
              No billing account linked. Subscribe from the{" "}
              <Link href="/#pricing" className="text-accent hover:text-accent-hover">
                pricing page
              </Link>
              .
            </p>
          )}
        </div>
      </Card>
    </div>
  );
}
