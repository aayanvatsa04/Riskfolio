drop trigger if exists price_history_set_updated_at on public.price_history;
drop function if exists public.set_price_history_updated_at();
drop table if exists public.price_history;

create table if not exists public.portfolios (
    user_id uuid not null references auth.users(id) on delete cascade,
    id text not null,
    name text not null,
    holdings jsonb not null default '[]'::jsonb,
    confidence_level integer not null,
    horizon integer not null,
    n_simulations integer not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint portfolios_pkey primary key (user_id, id),
    constraint portfolios_name_not_blank check (btrim(name) <> ''),
    constraint portfolios_holdings_is_array check (jsonb_typeof(holdings) = 'array'),
    constraint portfolios_confidence_level_valid check (confidence_level in (90, 95, 99)),
    constraint portfolios_horizon_positive check (horizon > 0),
    constraint portfolios_n_simulations_positive check (n_simulations > 0)
);

alter table public.portfolios enable row level security;

create index if not exists portfolios_user_updated_at_idx
    on public.portfolios (user_id, updated_at desc);

drop policy if exists "Users can read their own portfolios" on public.portfolios;
drop policy if exists "Users can insert their own portfolios" on public.portfolios;
drop policy if exists "Users can update their own portfolios" on public.portfolios;
drop policy if exists "Users can delete their own portfolios" on public.portfolios;

create policy "Users can read their own portfolios"
on public.portfolios
for select
to authenticated
using ((select auth.uid()) = user_id);

create policy "Users can insert their own portfolios"
on public.portfolios
for insert
to authenticated
with check ((select auth.uid()) = user_id);

create policy "Users can update their own portfolios"
on public.portfolios
for update
to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

create policy "Users can delete their own portfolios"
on public.portfolios
for delete
to authenticated
using ((select auth.uid()) = user_id);
