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
the isolated `crisis_contacts` table and is available only through a separately authorized,
audited operator endpoint. It must
not be copied into appeal metadata, appeal text, logs, audit metadata, or routing history.

Feedback comments and complaints are encrypted because free text can contain identifying
information. Assignment, status, and transfer reasons are operational metadata; future UI and
service validation must prevent sensitive applicant content from being copied into them.

## Anonymous track access

No raw track number is stored. Lookup normalizes a presented `ОТК-XXXX-XXXX` code in the
application and calculates `HMAC-SHA256(TRACK_HMAC_SECRET, normalized_track_code)`. Only the
32-byte digest is indexed in PostgreSQL. HMAC provides deterministic lookup while preventing
a database-only attacker from directly reading track codes. Ambiguous characters are excluded
from generated codes. A successful check creates a separate, signed, short-lived HttpOnly
cookie scoped to one appeal; it is not an applicant identity and is not accepted as staff
authentication. This does not replace rate limits,
sufficient code entropy, secure delivery, or constant-time authorization behavior.

The separate `RATE_LIMIT_HMAC_SECRET` pseudonymizes transient IP inputs before short-lived
Valkey counters are written for staff login, track checks, and submission. Raw IP values are
not persisted, logged, or associated with appeals. Neither HMAC secret is reused as the
content-encryption key.

## Internal staff authentication

Staff users are an explicit internal identity boundary and are not applicant identities.
Passwords are stored only as Argon2 hashes. Short-lived access JWTs remain in browser memory;
opaque refresh tokens remain in a scoped HttpOnly cookie and are represented in
`staff_sessions` only by a keyed HMAC-SHA256 digest. Session rows contain no IP address,
User-Agent, or device fingerprint. Refresh rotation, logout, account deactivation, and password
changes provide server-side revocation.

Administrative role membership does not imply access to appeal text, applicant-specialist
chat, or crisis contacts. Future appeal-level authorization must enforce the narrower operator
triage and expert assignment/participation rules in addition to role checks.

## Encryption boundary

Sensitive fields use AES-256-GCM with a fresh 96-bit random nonce for every encryption. The
binary envelope contains a key-version byte, nonce, and authenticated ciphertext/tag.
Additional Authenticated Data binds content, answers, crisis contacts, rejection explanations,
and attachments
to their record context. Key version 1 is supported now; a key management and rotation workflow is not yet
implemented.

`CONTENT_ENCRYPTION_KEY` is a URL-safe base64 encoding of exactly 32 random bytes. It remains
outside source control. Encryption protects stored content only while keys are kept separate
from the database and its backups; it does not protect plaintext while an authorized process
is actively handling it.

## Attachments and audit records

Attachment records use opaque storage keys and SHA-256 digests. Original filenames and public
URLs are forbidden because filenames commonly contain personal data. Accepted JPEG, PNG, and
WEBP files are decoded, dimension-bounded, orientation-corrected, and re-encoded from pixels so
EXIF/geolocation and unnecessary metadata are removed. Sanitized bytes are AES-GCM encrypted
into private filesystem storage. The stored digest and byte size describe the encrypted blob.
Malware scanning is not yet implemented.

## Crisis handling

Crisis detection is conservative phrase matching over plaintext already in memory for
submission. Only a boolean flag is retained; matched phrases are not logged or stored as new
metadata, and priority remains `standard` until a human changes it. The public help panel is
non-blocking and its contact resources are configuration that organizers must approve before
production. An explicitly supplied crisis contact reduces anonymity and is encrypted only in
the isolated `crisis_contacts` table.

Phase 4 crisis detection loads active literal phrases from `crisis_rules`. Rules are
administrator-managed metadata, never applicant content, and cannot contain executable regex.
Normalization handles Unicode compatibility, case, `ё`/`е`, punctuation, hyphens, and repeated
whitespace. Compact matching is an explicit per-rule choice. Matching retains only the appeal's
boolean crisis flag, never the matched phrase. Phase 6 will add administrator CRUD.

Operator serializers explicitly enumerate triage fields and omit chat and internal notes.
Administrator role alone does not grant this access. Applicant-visible rejection explanations
are encrypted separately; the text is absent from audit metadata and status-history reasons.
Attachment retrieval verifies the encrypted-blob digest and reveals no private storage path,
storage key, or original filename.

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
