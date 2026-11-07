---
title: Change Server Parameters via the RDS Parameter Template, Not ALTER SYSTEM
impact: HIGH
impactDescription: Parameter changes that actually apply; avoids permission errors and silently lost settings
tags: rds, parameters, alter-system, tuning, huawei-cloud
---

## Change Server Parameters via the RDS Parameter Template, Not ALTER SYSTEM

On Huawei Cloud RDS the application role is not a superuser: `ALTER SYSTEM` is denied, and SUSET parameters (such as `shared_preload_libraries`) cannot be set at session level either. Server parameters are managed through the console parameter template, then applied (with a restart where the parameter requires one).

**Incorrect (fails or silently does nothing):**

```sql
-- Permission denied on RDS: the role is not a superuser
alter system set max_connections = 200;

-- SUSET parameters also fail at session level
set log_lock_waits = on;
```

**Correct (console channel, then verify from SQL):**

```text
1. Console: RDS instance > Parameters > parameter template > edit parameter
2. Apply the template (restart the instance where required — e.g.
   max_connections, shared_preload_libraries)
```

```sql
-- Verify the effective value from SQL after the change
show max_connections;
select name, setting, pending_restart from pg_settings
where name in ('max_connections', 'shared_preload_libraries');
```

Reference: [Huawei Cloud RDS Documentation](https://support.huaweicloud.com/rds/index.html)
