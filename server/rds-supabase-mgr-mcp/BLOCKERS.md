# Remaining scope and dependencies — 2026-11-02

| Scene | Implemented | Remaining |
|---|---|---|
| Creation | Branch planning | Full creation validation/submit; supplied summary still omits password/timezone regexes, minimum managed version value and several nested constraints; secrets channel required |
| Deletion | App-only preview/submit, job query | PG cascade disabled: complete cross-product association visibility, terminal state and race handling required |
| Access | SSL and EIP preview/submit | Certificate list capture confirmed (CCM); native mapping, compatibility/purchase; application password input channel; cloud validation |
| Security group | Requirement scope recorded | Rule add/delete requests now supplied; ingress array builder validated. Creation capture uses v2 extension, not the earlier v3 route. Verified standalone VPC endpoint/auth mapping and response schemas still required. RDS instance SG replacement is not rule management |
| ApiKey | Metadata list and reset | Plaintext secure delivery; new-key correlation and job response schema. Backend confirms atomic old-deleted/new-normal transition after agent success; later workflow recovery steps still need separate verification |
| Business config | Auth query and explicit registration flags | SMTP/GitHub/templates/storage updates and secret channel; storage omit-SK vs required-SK contradiction |

Common: IAM token externally supplied; SDK Core AK/SK signing implemented; live IAM and generated UniSDK replacement unverified. Poll endpoint is known, but exact terminal schema remains open. Local expiring plans and a persistent one-use intent ledger are implemented. No verified job reconciliation/release, cross-machine deduplication or automatic recovery yet. Write timeouts are unknown outcomes, never retry automatically. Raw response shape and user permission visibility require integration verification.

No internal source reports or captures are included. These dependencies constrain corresponding operations, not all development.

Latest 2026-11-02 correction: SSL preview and acceptance include interruption warnings and manual Auth URL follow-up for both directions. No URL is automatically rewritten. VPC creation defaults allow outbound traffic but do not establish application ingress; application port defaults to 8443, not the mistyped 8843. Plaintext key API availability does not by itself establish secure delivery to a user.

Second backend review: Auth non-null fields replace old values; null/omitted preserve them (provider disable rules remain explicit exceptions). This does not resolve Storage required-SK contradiction. Certificate backend requests SSL/PostgreSQL context from CCM; private key handling stays backend-only. No additional browser replay is needed to establish these reported code semantics.


0.3.1a1: strict top-level input rejection and prepared-plan cancellation implemented. Cancellation is local only and fails for submitted/accepted/unknown. Remaining engineering includes live preview/state snapshots, resource-level concurrency control, whitelisted response schemas, layered completion results and evidence-driven ledger reconciliation. ApiKey reset still needs explicit key ownership/normal-state preflight and new-record correlation; app-level preflight is not enough for full scene acceptance.


0.3.2a1: application-scoped exact-ID/normal metadata preflight now protects key reset; status/type/ID/sorting filters and metadata whitelist are implemented. Name/time filters and post-reset new-key correlation remain pending. Workstation diagnostics provide offline/config checks and explicit read-only cloud probes; CodeArts remains the final collaborative stage.

Packaging dependency gate: installed huaweicloudsdkcore 3.1.220 metadata constrains pyasn1<=0.6.3, while the repository core uv policy overrides to >=0.6.4. The existing requirements-tested snapshot is not a security-approved release lock. A compatible dependency decision and security scan are required before a production bundle; do not silently apply --no-deps overrides for release. Target OS/Python-specific offline wheels remain to be assembled and verified.

SDK 0.3.7a1: SDK Core signing is implemented and locally tested. Generated Supabase models, live service authentication and job terminal interpretation remain unverified. See docs/SDK.md.

0.3.7a1: public RDS single-job status interpretation and bounded observations implemented. Supabase-specific live shape, resource/business verification and ledger reconciliation remain open. Creation field summary is supplied but does not close full validation/secrets gaps; see docs/SUPPLEMENT_REVIEW.md.

## 0.3.8a1交付边界
新增受保护本地请求引用、应用改密/Auth/OBS、原生VPC组和规则、创建候选查询。完整逐子场景范围以docs/SIX_SCENARIO_MATRIX.md为准；外部缺口见docs/OPEN_QUESTIONS.md。包周期创建、证书原生查询/购买、宿主秘密保险库及PG级联仍未交付。所有新增能力仅完成离线验证，真实环境与码道验收未完成。
