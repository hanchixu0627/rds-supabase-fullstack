---
title: Use request.jwt.claims for RLS Identity on PostgREST Tables
impact: CRITICAL
impactDescription: Working tenant isolation; the standard auth.uid() helper does not exist on this deployment
tags: rls, jwt, postgrest, identity, row-level-security
---

## Use request.jwt.claims for RLS Identity on PostgREST Tables

The auth schema on this deployment contains the GoTrue tables but no helper functions — `auth.uid()` does not exist. PostgREST injects the verified JWT payload as the `request.jwt.claims` setting; the `sub` claim holds the calling user's UUID.

**Incorrect (helper that does not exist here):**

```sql
-- Standard-stack pattern; fails on this deployment
create policy orders_policy on orders
  for select
  to authenticated
  using (user_id = auth.uid());  -- ERROR: function auth.uid() does not exist
```

**Correct (read identity from the JWT claims PostgREST injects):**

```sql
create policy orders_policy on orders
  for select
  to authenticated
  using (user_id = current_setting('request.jwt.claims', true)::jsonb ->> 'sub');

-- Wrap in (select ...) so the claim is parsed once per statement, not per row
create policy orders_policy on orders
  for select
  to authenticated
  using ((select current_setting('request.jwt.claims', true)::jsonb ->> 'sub') = user_id);
```

Alternatively, deploy `auth.uid()`-equivalent helper functions once as a platform bootstrap, after which standard-stack SQL patterns work unchanged — see `rds-auth-helpers`.

Reference: [Row Security Policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
