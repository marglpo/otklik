# Otklik MVP threat model

This document describes the Phase 2A security assumptions and limits. It is a living
model, not a claim that the current foundation is a complete production system.

## Assets

- Original appeal contents and encrypted intake answers
- Applicant/specialist chat messages
- Internal staff notes
- Optional crisis contact details
- Attachment contents and metadata
- Raw track access secrets and their lookup digests
- Staff credentials and future authenticated sessions
- Security audit records and cryptographic keys

## Primary threats

- A database or backup leak exposing operational metadata or ciphertext
- A stolen track number allowing unauthorized access to an appeal
- Brute-force or enumeration attacks against future track lookup
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

1. The applicant or staff browser, which will eventually handle plaintext before transport.
2. A future reverse proxy, which may terminate TLS and transiently observe network metadata.
3. FastAPI, which validates requests and will perform authorization and cryptography.
4. PostgreSQL, which stores operational metadata, HMAC digests, and encrypted sensitive
   fields.
5. Valkey, which will hold short-lived coordination and rate-limit state, not durable appeal
   content.
6. File storage, which will eventually store encrypted attachment bytes under opaque keys.

Connections between these boundaries require transport security in deployment. Application
authorization must be enforced even when infrastructure is on a private network.

## Current controls

- There is no applicant identity or account record.
- Appeal metadata is separated from encrypted content, chat, notes, intake answers, and
  crisis contacts.
- Raw track codes are not persisted; the schema reserves a unique HMAC-SHA256 digest.
- Sensitive database fields use a versioned AES-256-GCM envelope foundation.
- Crisis contacts and internal notes have dedicated tables to support narrow future access
  policy.
- Attachments store no original filename or public URL.
- Access logging is disabled and application logging policy forbids request bodies,
  authorization headers, secrets, and sensitive content.
- Audit metadata is restricted by policy to allowlisted, non-sensitive operational values.

## MVP limitations

Phase 2A is only a domain, persistence, and cryptographic foundation. Applicant submission,
track-code generation and lookup, rate limiting, staff authentication, RBAC, attachment
encryption/storage, audit-write allowlisting, backups, and deployment TLS are not yet
implemented. The presence of encrypted columns does not mean that a complete key-rotation or
key-custody process exists.

Otklik does **not** claim network-level anonymity. The application is designed not to persist
or associate client IP addresses or User-Agent values with appeals, but browsers, operating
systems, networks, a future reverse proxy, hosting providers, and other HTTP infrastructure
may transiently observe network metadata. Operational logging and retention must be reviewed
at every deployment boundary.
