import Link from "next/link";

export function MarketingFooter() {
  return (
    <footer className="border-t border-border bg-surface">
      <div className="max-w-6xl mx-auto px-6 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          <div className="col-span-1 md:col-span-2">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-7 h-7 bg-accent rounded-lg flex items-center justify-center">
                <span className="text-white font-bold text-sm">S</span>
              </div>
              <span className="font-semibold text-text-primary">
                SaaS Platform
              </span>
            </div>
            <p className="text-sm text-text-secondary max-w-sm">
              Your on-demand creative and engineering partner. Ship faster with
              a dedicated team.
            </p>
          </div>
          <div>
            <h4 className="text-sm font-semibold text-text-primary mb-4">
              Product
            </h4>
            <ul className="space-y-2">
              <li>
                <Link
                  href="/pricing"
                  className="text-sm text-text-secondary hover:text-text-primary transition-colors"
                >
                  Pricing
                </Link>
              </li>
              <li>
                <Link
                  href="/login"
                  className="text-sm text-text-secondary hover:text-text-primary transition-colors"
                >
                  Log in
                </Link>
              </li>
            </ul>
          </div>
          <div>
            <h4 className="text-sm font-semibold text-text-primary mb-4">
              Legal
            </h4>
            <ul className="space-y-2">
              <li>
                <span className="text-sm text-text-tertiary">
                  Privacy Policy
                </span>
              </li>
              <li>
                <span className="text-sm text-text-tertiary">
                  Terms of Service
                </span>
              </li>
            </ul>
          </div>
        </div>
        <div className="border-t border-border mt-8 pt-8 text-center">
          <p className="text-sm text-text-tertiary">
            &copy; {new Date().getFullYear()} SaaS Platform. All rights
            reserved.
          </p>
        </div>
      </div>
    </footer>
  );
}
