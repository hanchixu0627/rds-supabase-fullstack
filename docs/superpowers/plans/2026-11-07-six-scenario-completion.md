# Six-scenario completion implementation plan

Goal: expand the management MCP and separate Skill using verified contracts, retaining explicit release gates for missing contracts and live validation.
Architecture: retain tools/service/client boundaries and the existing confirmation ledger. Local operator-provisioned request aliases carry sensitive inputs; tool calls never contain secret values. Use native official VPC v3 contracts rather than console proxy shapes.
Spec: existing product REQUIREMENTS/OPEN_QUESTIONS and local 27-row scenario matrix, latest user-supplied backend summaries.

- [x] Add protected local request-reference input and strict per-operation field allowlists; test no secret exposure, reference mutation binding, unknown field rejection.
- [x] Implement application-only password change, partial Auth provider/URL/template update and explicit full Storage replacement using confirmed RDS paths. Preserve existing flag tool and ledger behavior.
- [x] Implement native VPC inventory/group/rule capabilities where official contracts are verified; use distinct service endpoint and permissions. Do not replace existing unrelated rules.
- [x] Expand creation candidate queries and request validation only where contracts are explicit; no guessed minimum engine/volume/password policy or guessed generated SDK methods.
- [x] Update Skill capability routing, acceptance and remaining gaps; test, review and publish incremental MR.

External gates remain: native certificate product/API compatibility, complete create policy, PG cascade authorization/association contract, secure plaintext Key delivery integration and live/Agent/CodeArts acceptance. These are not equivalent to complete six-scenario release. User has been asked for updated backend/UniSDK evidence while independent work proceeds.


Execution record 2026-11-07: request references, RDS mutations, VPC and creation candidate tests RED→GREEN; new user SDK specification then enabled Single creation, local key delivery and omitted-SK updates with additional RED→GREEN tests. Full suite: 124 passed, 93.09% coverage, 17 subtests. Independent reviewer found no confirmed blockers, including a scoped follow-up for the new SDK additions.

Ruling: native VPC v3 uses single security_group/security_group_rule objects, not Console proxy arrays; native201/204 results are not RDS jobs. Cost if incompatible with target region: fail closed and require adapter evidence.
Ruling: latest full SDK definitions supersede early abbreviated fragments; Single only, explicit creation branch, postPaid subset; unknown backend version/capacity/password policy remains backend authoritative. Cost: unsupported requests require backend evidence or product scope extension, not guessed defaults.
Ruling: Storage omitted SK requires already enabled storage and unchanged AK; first enable/credential change requires full credentials. Cost: intentionally narrower than a generic patch when identity cannot be verified.
Ruling: local operator file references and protected key output provide a development bridge, not a host secret vault; Windows ACL is operator-managed. Cost: production requires trusted account/host isolation validation.
No deferred reviewer findings. External gates remain documented; this plan completion covers implementable increment, not final production acceptance.
