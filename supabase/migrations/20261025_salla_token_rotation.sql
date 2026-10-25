-- Separate OAuth storage, leaves the original salla_stores table untouched.
-- Execute ONCE in Supabase SQL Editor after backing up the project.
create table if not exists public.salla_oauth_tokens (
  merchant_id text primary key,
  store_name text not null,
  access_token text not null,
  refresh_token text not null,
  installed_at timestamptz default now(),
  token_updated_at timestamptz not null default now(),
  expires_at timestamptz not null,
  connection_status text not null default 'connected'
    check (connection_status in ('connected', 'refreshing', 'review_required', 'reconnect_required')),
  last_refresh_attempt_at timestamptz,
  last_successful_refresh_at timestamptz,
  last_error text,
  lock_nonce uuid,
  lock_acquired_at timestamptz,
  updated_at timestamptz not null default now()
);
create index if not exists salla_oauth_token_due_idx on public.salla_oauth_tokens(connection_status, expires_at);
alter table public.salla_oauth_tokens enable row level security;
revoke all on public.salla_oauth_tokens from anon, authenticated;
-- service_role bypasses RLS and is held exclusively by the server-side Streamlit app/Edge Function.

-- Claim one due store in a single database transaction, with row locking.
-- Abandoned claims require manual review: an OAuth single-use token must never be retried after unknown outcome.
create or replace function public.salla_claim_due_tokens(p_limit integer default 5)
returns table (merchant_id text, refresh_token text, lock_nonce uuid)
language plpgsql security definer set search_path = ''
as $$
begin
  return query
  with picked as (
    select t.merchant_id
    from public.salla_oauth_tokens t
    where t.connection_status = 'connected'
      and t.expires_at <= now() + interval '3 days'
    order by t.expires_at asc
    for update skip locked
    limit greatest(1, least(coalesce(p_limit, 5), 10))
  ), updated as (
    update public.salla_oauth_tokens t
      set connection_status = 'refreshing',
          lock_nonce = gen_random_uuid(),
          lock_acquired_at = now(),
          last_refresh_attempt_at = now(),
          last_error = null,
          updated_at = now()
    where t.merchant_id in (select p.merchant_id from picked p)
    returning t.merchant_id, t.refresh_token, t.lock_nonce
  )
  select updated.merchant_id, updated.refresh_token, updated.lock_nonce from updated;
end;
$$;

create or replace function public.salla_complete_rotation(
  p_merchant_id text, p_lock_nonce uuid,
  p_access_token text, p_refresh_token text, p_expires_in integer default 1209600
) returns boolean
language plpgsql security definer set search_path = ''
as $$
begin
  if coalesce(length(p_access_token), 0) < 10 or coalesce(length(p_refresh_token), 0) < 10 then
    raise exception 'OAuth response is incomplete';
  end if;
  update public.salla_oauth_tokens t
  set access_token = p_access_token, refresh_token = p_refresh_token,
      expires_at = now() + make_interval(secs => greatest(600, least(coalesce(p_expires_in, 1209600), 1209600))),
      token_updated_at = now(), last_successful_refresh_at = now(),
      connection_status = 'connected', last_error = null,
      lock_nonce = null, lock_acquired_at = null, updated_at = now()
  where t.merchant_id = p_merchant_id and t.lock_nonce = p_lock_nonce
    and t.connection_status = 'refreshing';
  return found;
end;
$$;

create or replace function public.salla_mark_refresh_error(
  p_merchant_id text, p_lock_nonce uuid,
  p_reason text, p_reconnect boolean default false
) returns boolean
language plpgsql security definer set search_path = ''
as $$
begin
  update public.salla_oauth_tokens t
  set connection_status = case when p_reconnect then 'reconnect_required' else 'review_required' end,
      last_error = left(coalesce(p_reason, 'unspecified error'), 160),
      lock_nonce = null, lock_acquired_at = null, updated_at = now()
  where t.merchant_id = p_merchant_id and t.lock_nonce = p_lock_nonce
    and t.connection_status = 'refreshing';
  return found;
end;
$$;

-- If a claim remains after an unknown failure, quarantine it rather than retrying.
create or replace function public.salla_quarantine_abandoned_refreshes()
returns integer language plpgsql security definer set search_path = ''
as $$
declare n integer;
begin
  update public.salla_oauth_tokens t
     set connection_status='review_required', last_error='Refresh result unknown; manual review required',
         lock_nonce=null, lock_acquired_at=null, updated_at=now()
  where t.connection_status='refreshing' and t.lock_acquired_at < now() - interval '15 minutes';
  get diagnostics n = row_count;
  return n;
end;
$$;

revoke all on function public.salla_claim_due_tokens(integer) from public, anon, authenticated;
revoke all on function public.salla_complete_rotation(text,uuid,text,text,integer) from public, anon, authenticated;
revoke all on function public.salla_mark_refresh_error(text,uuid,text,boolean) from public, anon, authenticated;
revoke all on function public.salla_quarantine_abandoned_refreshes() from public, anon, authenticated;
grant execute on function public.salla_claim_due_tokens(integer) to service_role;
grant execute on function public.salla_complete_rotation(text,uuid,text,text,integer) to service_role;
grant execute on function public.salla_mark_refresh_error(text,uuid,text,boolean) to service_role;
grant execute on function public.salla_quarantine_abandoned_refreshes() to service_role;
