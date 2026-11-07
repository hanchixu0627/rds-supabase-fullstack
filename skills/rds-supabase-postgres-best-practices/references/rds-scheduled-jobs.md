---
title: Schedule Background Jobs with pg_cron
impact: HIGH
impactDescription: Database-native scheduled jobs; avoids the timezone trap and the missing-preload startup failure
tags: pg-cron, scheduled-jobs, scheduling, rds
---

## Schedule Background Jobs with pg_cron

Scheduled maintenance (cleanup, rollups, refreshes) runs inside the database with pg_cron. If the extension is not yet active on the instance, an administrator must enable it through the RDS parameter template (`shared_preload_libraries` plus `cron.database_name`) and restart before the extension can be created.

**Incorrect (app-process timers, or ignoring that pg_cron runs in UTC):**

```sql
-- Scheduling from the application process: jobs die on every deploy,
-- no run history, silent misses
select cron.schedule('cleanup', '0 3 * * *', 'delete from sessions where expires_at < now()');
-- pg_cron evaluates schedules in UTC: '0 3 * * *' fires at 03:00 UTC, not local time
```

**Correct (database-native, UTC-aware, inspectable):**

```sql
-- Precondition (administrator, once): RDS console parameter template
--   shared_preload_libraries = 'pg_cron', cron.database_name = <this database>, restart

create extension if not exists pg_cron;

-- Express the schedule in UTC and comment the intended local time
select cron.schedule('cleanup-expired-sessions', '0 19 * * *',  -- 03:00 UTC+8
  'delete from public.sessions where expires_at < now()');

-- Inspect runs and manage jobs
select jobid, schedule, command from cron.job;
select * from cron.job_run_details order by start_time desc limit 10;
select cron.unschedule('cleanup-expired-sessions');
```

Reference: [pg_cron](https://github.com/citusdata/pg_cron)
