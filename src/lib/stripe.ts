import Stripe from "stripe";

export const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!, {
  apiVersion: "2025-03-31.basil",
  typescript: true,
});

export function getStripePrice(plan: "A" | "B"): string {
  if (plan === "A") return process.env.STRIPE_PRICE_ID_PLAN_A!;
  return process.env.STRIPE_PRICE_ID_PLAN_B!;
}

export function getPlanFromPrice(priceId: string): "A" | "B" | null {
  if (priceId === process.env.STRIPE_PRICE_ID_PLAN_A) return "A";
  if (priceId === process.env.STRIPE_PRICE_ID_PLAN_B) return "B";
  return null;
}
