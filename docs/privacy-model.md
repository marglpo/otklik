# Otklik privacy model

Otklik uses data minimization and separation as its baseline. Anonymous applicants do not
have accounts, user rows, profiles, or durable device identities. The application schema does
not persist applicant names, email addresses, phone numbers, schools, IP addresses,
User-Agent values, device/browser fingerprints, advertising IDs, or analytics identifiers.

## Data separation

The `appeals` table contains operational routing and lifecycle metadata only. Original appeal
text lives in one-to-one `appeal_contents` ciphertext. Sensitive questionnaire data is a
single encrypted payload in `appeal_intake_answers`. Applicant/specialist chat and internal
staff notes are separate encrypted tables so future authorization cannot confuse the two.

The optional crisis contact is the only explicit contact-data exception. It is encrypted in
the isolated `crisis_contacts` table and is intended for future operator-only access. It must
not be copied into appeal metadata, appeal text, logs, audit metadata, or routing history.

Feedback comments and complaints are encrypted because free text can contain identifying
information. Assignment, status, and transfer reasons are operational metadata; future UI and
service validation must prevent sensitive applicant content from being copied into them.

## Anonymous track access

No raw track number is stored. Future lookup will normalize a presented track code in the
application and calculate `HMAC-SHA256(TRACK_HMAC_SECRET, normalized_track_code)`. Only the
32-byte digest is indexed in PostgreSQL. HMAC provides deterministic lookup while preventing
a database-only attacker from directly reading track codes; it does not replace rate limits,
sufficient code entropy, secure delivery, or constant-time authorization behavior.

The separate `RATE_LIMIT_HMAC_SECRET` is reserved for pseudonymizing transient rate-limit
inputs. Neither HMAC secret is reused as the content-encryption key.

## Encryption boundary

Sensitive fields use AES-256-GCM with a fresh 96-bit random nonce for every encryption. The
binary envelope contains a key-version byte, nonce, and authenticated ciphertext/tag. Optional
Additional Authenticated Data can bind ciphertext to contextual identifiers in future service
logic. Key version 1 is supported now; a key management and rotation workflow is not yet
implemented.

`CONTENT_ENCRYPTION_KEY` is a URL-safe base64 encoding of exactly 32 random bytes. It remains
outside source control. Encryption protects stored content only while keys are kept separate
from the database and its backups; it does not protect plaintext while an authorized process
is actively handling it.

## Attachments and audit records

Attachment records use opaque storage keys and SHA-256 content digests. Original filenames
and public URLs are forbidden because filenames commonly contain personal data. File bytes,
file encryption, metadata stripping, malware scanning, and upload APIs are future work.

Audit records may contain allowlisted operational metadata only. Audit `reason` and
`metadata_json` must never contain appeal or chat text, internal notes, crisis contacts,
passwords, access tokens, raw track numbers, or encryption keys. The polymorphic `entity_id`
has no foreign key by design.

## Network and operational limits

The application avoids persisting or associating IP/User-Agent values with appeals, but this
is not a claim of network-level anonymity. HTTP infrastructure may transiently observe IP
addresses and related metadata. Deployment proxy logs, platform logs, backups, staff access,
key custody, and retention settings remain part of the privacy boundary and require explicit
hardening in later phases.
