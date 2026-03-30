-- ============================================
-- SaaS Platform Database Schema
-- Run this in the Supabase SQL editor
-- ============================================

-- Enable UUID generation
create extension if not exists "uuid-ossp";

-- ============================================
-- ENUM TYPES
-- ============================================

create type user_role as enum ('admin', 'worker', 'client');
create type subscription_plan as enum ('A', 'B');
create type subscription_status as enum ('active', 'canceled', 'past_due', 'trialing');
create type task_status as enum ('submitted', 'in_progress', 'internal_review', 'client_review', 'completed');
create type file_type as enum ('brief', 'deliverable');

-- ============================================
-- TABLES
-- ============================================

create table public.users (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null unique,
  full_name text,
  role user_role not null default 'client',
  created_at timestamptz not null default now()
);

create table public.clients (
  id uuid primary key default uuid_generate_v4(),
  user_id uuid not null unique references public.users(id) on delete cascade,
  stripe_customer_id text unique,
  subscription_id text unique,
  plan subscription_plan,
  status subscription_status not null default 'active',
  created_at timestamptz not null default now()
);

create table public.tasks (
  id uuid primary key default uuid_generate_v4(),
  client_id uuid not null references public.clients(id) on delete cascade,
  assigned_to uuid references public.users(id) on delete set null,
  title text not null,
  description text not null default '',
  status task_status not null default 'submitted',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.task_files (
  id uuid primary key default uuid_generate_v4(),
  task_id uuid not null references public.tasks(id) on delete cascade,
  file_url text not null,
  file_name text not null,
  uploaded_by uuid not null references public.users(id) on delete cascade,
  file_type file_type not null default 'brief',
  created_at timestamptz not null default now()
);

create table public.comments (
  id uuid primary key default uuid_generate_v4(),
  task_id uuid not null references public.tasks(id) on delete cascade,
  user_id uuid not null references public.users(id) on delete cascade,
  content text not null,
  created_at timestamptz not null default now()
);

create table public.status_updates (
  id uuid primary key default uuid_generate_v4(),
  task_id uuid not null references public.tasks(id) on delete cascade,
  old_status task_status,
  new_status task_status not null,
  changed_by uuid not null references public.users(id) on delete cascade,
  created_at timestamptz not null default now()
);

-- CMS tables for marketing site
create table public.site_content (
  id uuid primary key default uuid_generate_v4(),
  page text not null,
  section text not null,
  content jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(page, section)
);

create table public.pricing_tiers (
  id uuid primary key default uuid_generate_v4(),
  name text not null,
  plan subscription_plan not null unique,
  price integer not null,
  features text[] not null default '{}',
  stripe_price_id text not null,
  created_at timestamptz not null default now()
);

create table public.faqs (
  id uuid primary key default uuid_generate_v4(),
  question text not null,
  answer text not null,
  sort_order integer not null default 0,
  created_at timestamptz not null default now()
);

-- ============================================
-- INDEXES
-- ============================================

create index idx_tasks_client_id on public.tasks(client_id);
create index idx_tasks_assigned_to on public.tasks(assigned_to);
create index idx_tasks_status on public.tasks(status);
create index idx_task_files_task_id on public.task_files(task_id);
create index idx_comments_task_id on public.comments(task_id);
create index idx_status_updates_task_id on public.status_updates(task_id);
create index idx_clients_user_id on public.clients(user_id);

-- ============================================
-- AUTO-UPDATE updated_at TRIGGER
-- ============================================

create or replace function public.handle_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger on_task_updated
  before update on public.tasks
  for each row execute function public.handle_updated_at();

create trigger on_site_content_updated
  before update on public.site_content
  for each row execute function public.handle_updated_at();

-- ============================================
-- AUTO-CREATE USER PROFILE ON SIGNUP
-- ============================================

create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.users (id, email, full_name, role)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data->>'full_name', ''),
    coalesce((new.raw_user_meta_data->>'role')::user_role, 'client')
  );
  return new;
end;
$$ language plpgsql security definer;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ============================================
-- ROW LEVEL SECURITY POLICIES
-- ============================================

alter table public.users enable row level security;
alter table public.clients enable row level security;
alter table public.tasks enable row level security;
alter table public.task_files enable row level security;
alter table public.comments enable row level security;
alter table public.status_updates enable row level security;
alter table public.site_content enable row level security;
alter table public.pricing_tiers enable row level security;
alter table public.faqs enable row level security;

-- Helper: get the current user's role
create or replace function public.get_user_role()
returns user_role as $$
  select role from public.users where id = auth.uid();
$$ language sql security definer stable;

-- Helper: get the current user's client id
create or replace function public.get_client_id()
returns uuid as $$
  select id from public.clients where user_id = auth.uid();
$$ language sql security definer stable;

-- USERS table policies
create policy "Users can read own profile"
  on public.users for select
  using (id = auth.uid());

create policy "Admins can read all users"
  on public.users for select
  using (public.get_user_role() = 'admin');

create policy "Users can update own profile"
  on public.users for update
  using (id = auth.uid());

-- CLIENTS table policies
create policy "Clients can read own record"
  on public.clients for select
  using (user_id = auth.uid());

create policy "Admins can read all clients"
  on public.clients for select
  using (public.get_user_role() = 'admin');

create policy "Admins can update clients"
  on public.clients for update
  using (public.get_user_role() = 'admin');

-- TASKS table policies
create policy "Clients can read own tasks"
  on public.tasks for select
  using (client_id = public.get_client_id());

create policy "Clients can insert own tasks"
  on public.tasks for insert
  with check (client_id = public.get_client_id());

create policy "Workers can read assigned tasks"
  on public.tasks for select
  using (assigned_to = auth.uid());

create policy "Workers can update assigned tasks"
  on public.tasks for update
  using (assigned_to = auth.uid());

create policy "Admins can do anything with tasks"
  on public.tasks for all
  using (public.get_user_role() = 'admin');

-- TASK FILES policies
create policy "Users can read files for visible tasks"
  on public.task_files for select
  using (
    exists (
      select 1 from public.tasks t
      where t.id = task_id
      and (
        t.client_id = public.get_client_id()
        or t.assigned_to = auth.uid()
        or public.get_user_role() = 'admin'
      )
    )
  );

create policy "Authenticated users can upload files"
  on public.task_files for insert
  with check (uploaded_by = auth.uid());

create policy "Admins can manage files"
  on public.task_files for all
  using (public.get_user_role() = 'admin');

-- COMMENTS policies
create policy "Users can read comments for visible tasks"
  on public.comments for select
  using (
    exists (
      select 1 from public.tasks t
      where t.id = task_id
      and (
        t.client_id = public.get_client_id()
        or t.assigned_to = auth.uid()
        or public.get_user_role() = 'admin'
      )
    )
  );

create policy "Authenticated users can create comments"
  on public.comments for insert
  with check (user_id = auth.uid());

create policy "Admins can manage comments"
  on public.comments for all
  using (public.get_user_role() = 'admin');

-- STATUS UPDATES policies
create policy "Users can read status updates for visible tasks"
  on public.status_updates for select
  using (
    exists (
      select 1 from public.tasks t
      where t.id = task_id
      and (
        t.client_id = public.get_client_id()
        or t.assigned_to = auth.uid()
        or public.get_user_role() = 'admin'
      )
    )
  );

create policy "Authenticated users can create status updates"
  on public.status_updates for insert
  with check (changed_by = auth.uid());

-- SITE CONTENT - public read, admin write
create policy "Anyone can read site content"
  on public.site_content for select
  using (true);

create policy "Admins can manage site content"
  on public.site_content for all
  using (public.get_user_role() = 'admin');

-- PRICING TIERS - public read
create policy "Anyone can read pricing tiers"
  on public.pricing_tiers for select
  using (true);

create policy "Admins can manage pricing tiers"
  on public.pricing_tiers for all
  using (public.get_user_role() = 'admin');

-- FAQS - public read
create policy "Anyone can read FAQs"
  on public.faqs for select
  using (true);

create policy "Admins can manage FAQs"
  on public.faqs for all
  using (public.get_user_role() = 'admin');

-- ============================================
-- STORAGE BUCKETS
-- ============================================

insert into storage.buckets (id, name, public)
values ('briefs', 'briefs', false);

insert into storage.buckets (id, name, public)
values ('deliverables', 'deliverables', false);

-- Storage policies for briefs bucket
create policy "Authenticated users can upload briefs"
  on storage.objects for insert
  with check (bucket_id = 'briefs' and auth.role() = 'authenticated');

create policy "Users can read own briefs"
  on storage.objects for select
  using (bucket_id = 'briefs' and auth.role() = 'authenticated');

-- Storage policies for deliverables bucket
create policy "Workers and admins can upload deliverables"
  on storage.objects for insert
  with check (bucket_id = 'deliverables' and auth.role() = 'authenticated');

create policy "Authenticated users can read deliverables"
  on storage.objects for select
  using (bucket_id = 'deliverables' and auth.role() = 'authenticated');

-- ============================================
-- SEED DATA (Marketing content)
-- ============================================

insert into public.site_content (page, section, content) values
('home', 'hero', '{"title": "Ship faster with a dedicated design & dev team", "subtitle": "Your on-demand creative and engineering partner. Submit tasks, track progress, and receive polished deliverables — all in one place.", "cta_text": "Get Started", "cta_link": "/pricing"}'),
('home', 'features', '{"items": [{"title": "Unlimited Requests", "description": "Submit as many tasks as you need. We work through them one at a time with lightning speed.", "icon": "layers"}, {"title": "Fixed Monthly Rate", "description": "No surprises. Pay one flat fee per month for dedicated access to our team.", "icon": "credit-card"}, {"title": "Fast Turnaround", "description": "Most tasks completed within 48 hours. Larger projects scoped and delivered on schedule.", "icon": "zap"}, {"title": "Real-time Tracking", "description": "Watch your tasks move through our pipeline with live status updates and comments.", "icon": "activity"}]}'),
('home', 'how_it_works', '{"steps": [{"step": 1, "title": "Subscribe", "description": "Pick the plan that fits your needs and start your subscription."}, {"step": 2, "title": "Submit", "description": "Send us your tasks with briefs, references, and files."}, {"step": 3, "title": "Review", "description": "We deliver, you review, and request revisions until it is perfect."}]}');

insert into public.pricing_tiers (name, plan, price, features, stripe_price_id) values
('Standard', 'A', 3500, ARRAY['One active task at a time', 'Unlimited requests', '48-hour turnaround', 'Dedicated project manager', 'Pause or cancel anytime'], 'price_plan_a_placeholder'),
('Pro', 'B', 5500, ARRAY['Two active tasks at a time', 'Unlimited requests', '24-hour turnaround', 'Dedicated project manager', 'Priority support', 'Pause or cancel anytime', 'Strategy consultation calls'], 'price_plan_b_placeholder');

insert into public.faqs (question, answer, sort_order) values
('How does the subscription work?', 'Once subscribed, you can submit unlimited design and development requests. We work through them based on priority, delivering completed work for your review.', 1),
('What counts as a single task?', 'A task is a self-contained unit of work — a landing page, a logo concept, a component build, etc. Complex projects are broken into multiple tasks.', 2),
('How do revisions work?', 'Every deliverable goes through a review cycle. You can request as many revisions as needed until you are satisfied with the result.', 3),
('Can I pause my subscription?', 'Yes. You can pause your subscription at any time from the billing portal and resume when you are ready.', 4),
('Who will be working on my tasks?', 'You get access to our vetted team of senior designers and developers. An admin assigns each task to the best-fit team member.', 5),
('What if I do not like the work?', 'We iterate until you love it. If after revisions you are still not satisfied, we will work with you to find the right solution.', 6);

-- ============================================
-- ENABLE REALTIME
-- ============================================

alter publication supabase_realtime add table public.tasks;
alter publication supabase_realtime add table public.comments;
alter publication supabase_realtime add table public.status_updates;
