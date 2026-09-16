# Security

## Tenant isolation

Workspace authorization is enforced in routers and again in retrieval. Security tests create identically themed documents in two workspaces and assert that retrieval from one never returns the other's chunks.

## Authentication

Passwords use Argon2. Access tokens are short-lived JWTs. Refresh tokens are random opaque values; only SHA-256 hashes are stored. Refresh use rotates/revokes the previous session token. Users can list and revoke device sessions. Password reset revokes active sessions.

## File access

Source objects are private. S3-compatible production storage returns short-lived signed URLs only after a workspace permission check. Local development routes stream files only after the same authorization check.

## Uploads

Upload validation checks allowlisted MIME types, matching extensions, file size and sanitized names. Production deployments should attach a malware scanner (ClamAV or cloud scanner) before moving a document beyond validation.

## Web controls

API and web responses include baseline security headers. CORS is origin-scoped. The product does not render arbitrary HTML from documents; Markdown rendering should remain sanitized when raw HTML support is introduced.

## Privacy

Document deletion removes source objects and cascades pages/chunks/embeddings. Account deletion removes objects owned by the user's workspaces before SQL deletion. Admin analytics are aggregate by design.

## Secrets

`.env` is ignored. Production secrets belong in the deployment platform's secret manager. Never store provider keys in Git or client bundles.
