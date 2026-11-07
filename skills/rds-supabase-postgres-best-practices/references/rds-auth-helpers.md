---
title: Deploy Identity Helper Functions as a Platform Bootstrap
impact: HIGH
impactDescription: auth.uid()-style helpers make standard-stack SQL patterns work unchanged; one policy-parsing pattern instead of many
tags: rls, jwt, bootstrap, identity, helper
---

## Deploy Identity Helper Functions as a Platform Bootstrap

The standard Supabase initialization SQL (helper functions such as `auth.uid()`) was not applied on this deployment. Deploying minimal, equivalent helpers once makes SQL written for the standard stack — documentation, examples, existing policies — work unchanged, and keeps every policy reading identity the same way.

**Incorrect (every policy re-parses the claims inline):**

```sql
-- Verbose and inconsistent; each policy must remember the full expression
create policy orders_policy on orders
  for select
  to authenticated
  using (user_id = current_setting('request.jwt.claims', true)::jsonb ->> 'sub');

create policy invoices_policy on invoices
  for select
  to authenticated
  using (user_id = current_setting('request.jwt.claims', true)::jsonb ->> 'sub');
```

**Correct (one-time bootstrap, then one call site per policy):**

```sql
-- One-time bootstrap: minimal helper, narrow grants
create or replace function auth.uid()
returns uuid
language sql
stable
as $$
  select nullif(current_setting('request.jwt.claims', true)::jsonb ->> 'sub', '')::uuid
$$;

revoke all on function auth.uid() from public;
grant execute on function auth.uid() to anon, authenticated, service_role;

-- Policies now read like the standard Supabase patterns
create policy orders_policy on orders
  for select
  to authenticated
  using ((select auth.uid()) = user_id);
```

If the current role cannot create functions in the `auth` schema, use a dedicated schema (for example `app`) and adjust call sites accordingly. Keep the `(select ...)` InitPlan wrapper in policies — see `security-rls-performance`.

Reference: [Row Security Policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
