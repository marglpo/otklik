# Otklik MVP threat model

This document describes the Phase 3 security assumptions and limits. It is a living
model, not a claim that the current foundation is a complete production system.

## Assets

- Original appeal contents and encrypted intake answers
- Applicant/specialist chat messages
- Internal staff notes
- Optional crisis contact details
- Attachment contents and metadata
- Raw track access secrets and their lookup digests
- Staff credentials and authenticated sessions
- Security audit records and cryptographic keys

## Primary threats

- A database or backup leak exposing operational metadata or ciphertext
- A stolen track number allowing unauthorized access to an appeal
- Brute-force or enumeration attacks against track lookup
- A compromised staff account reading or changing appeals
- Excessive staff permissions, including experts seeing operator-only crisis contacts or
  complaints
- Application, proxy, or infrastructure logs leaking appeal content, credentials, tokens,
  authorization headers, contact data, or raw track numbers
- Attachment filenames, embedded metadata, storage paths, or public URLs leaking identity
- Accidental administrator access to sensitive text without a justified operational need
- Database snapshots, storage backups, or encryption-key backups being exposed together
- Key or nonce misuse weakening encrypted content protection

## Trust boundaries

Data crosses the following boundaries:

1. The applicant or staff browser, which handles plaintext before transport.
2. A future reverse proxy, which may terminate TLS and transiently observe network metadata.
3. FastAPI, which validates requests and will perform authorization and cryptography.
4. PostgreSQL, which stores operational metadata, HMAC digests, and encrypted sensitive
   fields.
5. Valkey, which will hold short-lived coordination and rate-limit state, not durable appeal
   content.
6. Private file storage, which stores encrypted attachment bytes under opaque keys.

Connections between these boundaries require transport security in deployment. Application
authorization must be enforced even when infrastructure is on a private network.

## Current controls

- There is no applicant identity or account record.
- Appeal metadata is separated from encrypted content, chat, notes, intake answers, and
  crisis contacts.
- Raw track codes are returned only at creation and never persisted; lookup uses the unique
  HMAC-SHA256 digest.
- Successful track verification creates a short-lived signed HttpOnly capability scoped to
  one appeal.
- Sensitive database fields use a versioned AES-256-GCM envelope foundation.
- Crisis contacts and internal notes have dedicated tables to support narrow future access
  policy.
- Images are magic-byte checked, decoded with pixel bounds, re-encoded without source metadata,
  AES-GCM encrypted, and placed in private storage without an original filename or public URL.
- Public track checks and submissions use expiring Valkey counters keyed only by an HMAC of the
  transient network address.
- Crisis matching stores only a boolean and does not automatically escalate priority; support
  contacts remain organizer-controlled configuration.
- Access logging is disabled and application logging policy forbids request bodies,
  authorization headers, secrets, and sensitive content.
- Audit metadata is restricted by policy to allowlisted, non-sensitive operational values.
- Staff passwords use Argon2; short-lived access JWTs are bound to revocable server-side
  sessions through a session-ID claim.
- Refresh tokens are high entropy, rotate on use, stay in an HttpOnly cookie, and are stored
  only as keyed HMAC digests. Session records contain no network or device identity.
- Staff login attempts use expiring Valkey counters whose IP/login components are HMAC
  pseudonyms, not raw values.
- Central role guards distinguish unauthenticated (401) from unauthorized (403) requests, and
  the policy boundary explicitly denies sensitive content based on admin role alone.

## MVP limitations

Phase 3 adds anonymous submission and appeal-scoped status access, not staff appeal workflows
or complete application authorization. There is no applicant-specialist chat API, staff
attachment retrieval, malware scanner, storage retention lifecycle, audit-write allowlisting,
backup policy, or deployment TLS configuration. Phrase-based crisis detection can miss novel
wording and can produce false positives; it is not a clinical assessment. Crisis-help contacts
must be approved by organizers before production. Valkey rate limits reduce straightforward
abuse but do not replace proxy-level or distributed abuse controls. A complete key-rotation
and key-custody process is also not implemented.

Otklik does **not** claim network-level anonymity. The application is designed not to persist
or associate client IP addresses or User-Agent values with appeals, but browsers, operating
systems, networks, a future reverse proxy, hosting providers, and other HTTP infrastructure
may transiently observe network metadata. Operational logging and retention must be reviewed
at every deployment boundary.
