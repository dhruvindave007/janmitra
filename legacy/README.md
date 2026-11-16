# Legacy code

`backend-snapshot-2026-04/` is an earlier copy of the Django backend that used to live at the
repository root as `Janmitraapp/`. It was superseded by [`../backend/`](../backend), which is the
only tree that is built by the Dockerfile, run by `docker-compose.yml`, and covered by tests.

It is kept for reference only:

- it is missing later migrations (police stations, device tokens, V2 incident location);
- it is not imported, built, or deployed by anything in this repository;
- do not apply fixes here — change `backend/` instead.

It can be deleted once nobody needs to diff against it.
