create table if not exists public.price_history (
    ticker text not null,
    price_date date not null,
    adjusted_close double precision not null,
    source text not null default 'yfinance',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint price_history_pkey primary key (ticker, price_date),
    constraint price_history_adjusted_close_positive check (adjusted_close > 0)
);

alter table public.price_history enable row level security;

create index if not exists price_history_price_date_idx
    on public.price_history (price_date);

create index if not exists price_history_ticker_price_date_idx
    on public.price_history (ticker, price_date desc);

create or replace function public.set_price_history_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists price_history_set_updated_at on public.price_history;

create trigger price_history_set_updated_at
before update on public.price_history
for each row
execute function public.set_price_history_updated_at();
