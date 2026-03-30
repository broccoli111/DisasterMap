import { createClient } from "@/lib/supabase/server";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import Link from "next/link";

export default async function AdminClientsPage() {
  const supabase = await createClient();

  const { data: clients } = await supabase
    .from("clients")
    .select("*, user:users(full_name, email)")
    .order("created_at", { ascending: false });

  const subStatusVariant: Record<string, "success" | "error" | "warning" | "default"> = {
    active: "success",
    canceled: "error",
    past_due: "warning",
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Clients</h1>
        <p className="text-sm text-text-secondary mt-1">
          View and manage all client accounts.
        </p>
      </div>

      {clients && clients.length > 0 ? (
        <Card padding={false}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left p-4 font-medium text-text-secondary">
                    Name
                  </th>
                  <th className="text-left p-4 font-medium text-text-secondary">
                    Email
                  </th>
                  <th className="text-left p-4 font-medium text-text-secondary">
                    Plan
                  </th>
                  <th className="text-left p-4 font-medium text-text-secondary">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {clients.map((client) => {
                  const userInfo = client.user as Record<string, string> | null;
                  return (
                    <tr
                      key={client.id}
                      className="hover:bg-surface-hover transition-colors"
                    >
                      <td className="p-4">
                        <Link
                          href={`/admin/clients/${client.id}`}
                          className="text-text-primary font-medium hover:text-accent"
                        >
                          {userInfo?.full_name || "—"}
                        </Link>
                      </td>
                      <td className="p-4 text-text-secondary">
                        {userInfo?.email}
                      </td>
                      <td className="p-4 text-text-secondary">
                        {client.plan ? `Plan ${client.plan}` : "—"}
                      </td>
                      <td className="p-4">
                        <Badge
                          variant={
                            subStatusVariant[client.status] || "default"
                          }
                        >
                          {client.status}
                        </Badge>
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
          title="No clients yet"
          description="Clients will appear here once they sign up and subscribe."
        />
      )}
    </div>
  );
}
