# Deployment

A production deployment should run web, API and workers separately with managed PostgreSQL/pgvector, managed Redis and private S3-compatible storage.

## Required production controls

- TLS at the edge and secure origin headers.
- Strong `APP_SECRET` from a secret manager.
- Private object bucket with lifecycle/versioning policy.
- PostgreSQL backups and point-in-time recovery.
- Redis persistence appropriate to queue durability requirements.
- Worker autoscaling by queue depth.
- Error tracking and structured log shipping.
- ClamAV/cloud malware scanner wired into the validation stage.
- Email delivery provider for verification/reset/invitations.
- OAuth credentials and verified redirect URIs before enabling Google/Apple sign-in.

Run `alembic upgrade head` before serving API traffic. `/health` indicates process liveness; `/ready` verifies database readiness.

For zero-downtime upgrades, deploy additive database changes first, roll API/workers, then remove deprecated fields in a later release.
