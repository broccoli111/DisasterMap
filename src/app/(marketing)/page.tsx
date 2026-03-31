import { isSupabaseConfigured, createClient } from "@/lib/supabase/server";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { PricingCard } from "@/components/pricing-card";
import { formatCurrency } from "@/lib/utils";
import type { SubscriptionPlan } from "@/types";

export const dynamic = "force-dynamic";

const fallbackHero = {
  title: "Ship faster with a dedicated design & dev team",
  subtitle:
    "Your on-demand creative and engineering partner. Submit tasks, track progress, and receive polished deliverables — all in one place.",
  cta_text: "Get Started",
  cta_link: "#pricing",
};

const fallbackFeatures = {
  items: [
    {
      title: "Unlimited Requests",
      description:
        "Submit as many tasks as you need. We work through them one at a time with lightning speed.",
      icon: "layers",
    },
    {
      title: "Fixed Monthly Rate",
      description:
        "No surprises. Pay one flat fee per month for dedicated access to our team.",
      icon: "credit-card",
    },
    {
      title: "Fast Turnaround",
      description:
        "Most tasks completed within 48 hours. Larger projects scoped and delivered on schedule.",
      icon: "zap",
    },
    {
      title: "Real-time Tracking",
      description:
        "Watch your tasks move through our pipeline with live status updates and comments.",
      icon: "activity",
    },
  ],
};

const fallbackSteps = {
  steps: [
    { step: 1, title: "Subscribe", description: "Pick the plan that fits your needs and start your subscription." },
    { step: 2, title: "Submit", description: "Send us your tasks with briefs, references, and files." },
    { step: 3, title: "Review", description: "We deliver, you review, and request revisions until it is perfect." },
  ],
};

const fallbackTiers = [
  {
    id: "a",
    name: "Standard",
    plan: "A" as SubscriptionPlan,
    price: 3500,
    features: [
      "One active task at a time",
      "Unlimited requests",
      "48-hour turnaround",
      "Dedicated project manager",
      "Pause or cancel anytime",
    ],
    stripe_price_id: "",
    created_at: "",
  },
  {
    id: "b",
    name: "Pro",
    plan: "B" as SubscriptionPlan,
    price: 5500,
    features: [
      "Two active tasks at a time",
      "Unlimited requests",
      "24-hour turnaround",
      "Dedicated project manager",
      "Priority support",
      "Pause or cancel anytime",
      "Strategy consultation calls",
    ],
    stripe_price_id: "",
    created_at: "",
  },
];

const fallbackFaqs = [
  { id: "1", question: "How does the subscription work?", answer: "Once subscribed, you can submit unlimited design and development requests. We work through them based on priority, delivering completed work for your review." },
  { id: "2", question: "What counts as a single task?", answer: "A task is a self-contained unit of work — a landing page, a logo concept, a component build, etc. Complex projects are broken into multiple tasks." },
  { id: "3", question: "How do revisions work?", answer: "Every deliverable goes through a review cycle. You can request as many revisions as needed until you are satisfied with the result." },
  { id: "4", question: "Can I pause my subscription?", answer: "Yes. You can pause your subscription at any time from the billing portal and resume when you are ready." },
  { id: "5", question: "Who will be working on my tasks?", answer: "You get access to our vetted team of senior designers and developers. An admin assigns each task to the best-fit team member." },
  { id: "6", question: "What if I do not like the work?", answer: "We iterate until you love it. If after revisions you are still not satisfied, we will work with you to find the right solution." },
];

async function getContent() {
  if (!isSupabaseConfigured()) {
    return {
      hero: fallbackHero,
      features: fallbackFeatures,
      howItWorks: fallbackSteps,
      tiers: fallbackTiers,
      faqs: fallbackFaqs,
    };
  }

  try {
    const supabase = await createClient();

    const [heroRes, featuresRes, howItWorksRes, tiersRes, faqsRes] =
      await Promise.all([
        supabase
          .from("site_content")
          .select("content")
          .eq("page", "home")
          .eq("section", "hero")
          .single(),
        supabase
          .from("site_content")
          .select("content")
          .eq("page", "home")
          .eq("section", "features")
          .single(),
        supabase
          .from("site_content")
          .select("content")
          .eq("page", "home")
          .eq("section", "how_it_works")
          .single(),
        supabase.from("pricing_tiers").select("*").order("price"),
        supabase.from("faqs").select("*").order("sort_order"),
      ]);

    return {
      hero: (heroRes.data?.content as Record<string, string>) || fallbackHero,
      features:
        (featuresRes.data?.content as typeof fallbackFeatures) ||
        fallbackFeatures,
      howItWorks:
        (howItWorksRes.data?.content as typeof fallbackSteps) || fallbackSteps,
      tiers:
        tiersRes.data && tiersRes.data.length > 0
          ? tiersRes.data
          : fallbackTiers,
      faqs: faqsRes.data || fallbackFaqs,
    };
  } catch {
    return {
      hero: fallbackHero,
      features: fallbackFeatures,
      howItWorks: fallbackSteps,
      tiers: fallbackTiers,
      faqs: fallbackFaqs,
    };
  }
}

const featureIcons: Record<string, React.ReactNode> = {
  layers: (
    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6.429 9.75L2.25 12l4.179 2.25m0-4.5l5.571 3 5.571-3m-11.142 0L2.25 7.5 12 2.25l9.75 5.25-4.179 2.25m0 0L12 12.75 6.429 9.75m11.142 0l4.179 2.25-9.75 5.25-9.75-5.25 4.179-2.25" />
    </svg>
  ),
  "credit-card": (
    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 8.25h19.5M2.25 9h19.5m-16.5 5.25h6m-6 2.25h3m-3.75 3h15a2.25 2.25 0 002.25-2.25V6.75A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25v10.5A2.25 2.25 0 004.5 19.5z" />
    </svg>
  ),
  zap: (
    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
    </svg>
  ),
  activity: (
    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
    </svg>
  ),
};

export default async function HomePage() {
  const { hero, features, howItWorks, tiers, faqs } = await getContent();

  const heroTitle =
    (hero as Record<string, string>)?.title || fallbackHero.title;
  const heroSubtitle =
    (hero as Record<string, string>)?.subtitle || fallbackHero.subtitle;
  const ctaText =
    (hero as Record<string, string>)?.cta_text || fallbackHero.cta_text;
  const ctaLink =
    (hero as Record<string, string>)?.cta_link || fallbackHero.cta_link;

  const featureItems = (features as typeof fallbackFeatures)?.items || [];
  const steps = (howItWorks as typeof fallbackSteps)?.steps || [];

  return (
    <>
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="max-w-6xl mx-auto px-5 sm:px-6 py-16 sm:py-24 md:py-32">
          <div className="max-w-3xl mx-auto text-center">
            <h1 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-bold text-text-primary tracking-tight leading-tight">
              {heroTitle}
            </h1>
            <p className="mt-6 text-lg text-text-secondary max-w-2xl mx-auto">
              {heroSubtitle}
            </p>
            <div className="mt-8 flex items-center justify-center gap-4">
              <a href={ctaLink}>
                <Button size="lg">{ctaText}</Button>
              </a>
              <Link href="/login">
                <Button variant="outline" size="lg">
                  Log in
                </Button>
              </Link>
            </div>
          </div>
        </div>
        <div className="absolute inset-0 -z-10 bg-gradient-to-b from-accent-light/30 to-transparent" />
      </section>

      {/* Features */}
      {featureItems.length > 0 && (
        <section className="py-16 sm:py-20 bg-surface-secondary">
          <div className="max-w-6xl mx-auto px-5 sm:px-6">
            <h2 className="text-2xl sm:text-3xl font-bold text-text-primary text-center mb-8 sm:mb-12">
              Everything you need to move fast
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 sm:gap-8">
              {featureItems.map((feature) => (
                <div
                  key={feature.title}
                  className="bg-surface rounded-xl border border-border p-6 hover:shadow-md transition-shadow"
                >
                  <div className="w-10 h-10 rounded-lg bg-accent-light flex items-center justify-center text-accent mb-4">
                    {featureIcons[feature.icon] || featureIcons.layers}
                  </div>
                  <h3 className="text-base font-semibold text-text-primary mb-2">
                    {feature.title}
                  </h3>
                  <p className="text-sm text-text-secondary">
                    {feature.description}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* How it works */}
      {steps.length > 0 && (
        <section className="py-16 sm:py-20">
          <div className="max-w-4xl mx-auto px-5 sm:px-6">
            <h2 className="text-2xl sm:text-3xl font-bold text-text-primary text-center mb-8 sm:mb-12">
              How it works
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              {steps.map((step) => (
                <div key={step.step} className="text-center">
                  <div className="w-12 h-12 rounded-full bg-accent text-white flex items-center justify-center mx-auto mb-4 text-lg font-bold">
                    {step.step}
                  </div>
                  <h3 className="text-lg font-semibold text-text-primary mb-2">
                    {step.title}
                  </h3>
                  <p className="text-sm text-text-secondary">
                    {step.description}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Pricing */}
      <section id="pricing" className="py-16 sm:py-20 bg-surface-secondary scroll-mt-16">
        <div className="max-w-5xl mx-auto px-5 sm:px-6">
          <div className="text-center mb-10 sm:mb-14">
            <h2 className="text-2xl sm:text-3xl font-bold text-text-primary mb-4">
              Simple, transparent pricing
            </h2>
            <p className="text-lg text-text-secondary max-w-xl mx-auto">
              Choose the plan that fits your needs. No hidden fees. Pause or
              cancel anytime.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto">
            {tiers.map((tier) => (
              <PricingCard
                key={tier.id}
                name={tier.name}
                plan={tier.plan}
                price={formatCurrency(tier.price)}
                features={tier.features}
                highlighted={tier.plan === "B"}
              />
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      {faqs.length > 0 && (
        <section id="faq" className="py-16 sm:py-20 scroll-mt-16">
          <div className="max-w-3xl mx-auto px-5 sm:px-6">
            <h2 className="text-2xl sm:text-3xl font-bold text-text-primary text-center mb-8 sm:mb-12">
              Frequently asked questions
            </h2>
            <div className="space-y-4">
              {faqs.map((faq) => (
                <details
                  key={faq.id}
                  className="group bg-surface border border-border rounded-xl"
                >
                  <summary className="flex items-center justify-between cursor-pointer p-5 text-text-primary font-medium text-sm">
                    {faq.question}
                    <svg
                      className="w-5 h-5 text-text-tertiary transition-transform group-open:rotate-180 shrink-0 ml-4"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={1.5}
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M19.5 8.25l-7.5 7.5-7.5-7.5"
                      />
                    </svg>
                  </summary>
                  <div className="px-5 pb-5 text-sm text-text-secondary">
                    {faq.answer}
                  </div>
                </details>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* CTA */}
      <section className="py-16 sm:py-20 bg-surface-secondary">
        <div className="max-w-4xl mx-auto px-5 sm:px-6 text-center">
          <h2 className="text-2xl sm:text-3xl font-bold text-text-primary mb-4">
            Ready to ship faster?
          </h2>
          <p className="text-text-secondary mb-8 max-w-xl mx-auto">
            Join teams that use our platform to accelerate their design and
            development workflow.
          </p>
          <Link href="/signup">
            <Button size="lg">Get Started</Button>
          </Link>
        </div>
      </section>
    </>
  );
}
