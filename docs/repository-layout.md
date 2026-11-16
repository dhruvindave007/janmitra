# Repository layout

| Path | Status | Notes |
|------|--------|-------|
| `backend/` | **Live** | Django REST API. Built by `backend/Dockerfile`, orchestrated by `docker-compose.yml`. |
| `docker/` | **Live** | Nginx reverse-proxy configuration. |
| `scripts/` | Live (ops) | Deployment, backup and health-check scripts for the demo server. |
| `janmitra_mobile/` | **Live, source not in this repo** | Flutter app (citizen + officer roles). See below. |
| `mobile/` | Deprecated, source not in this repo | Earlier Flutter tree. See below. |
| `legacy/backend-snapshot-2026-04/` | Stale | Earlier copy of the backend, formerly `Janmitraapp/`. Reference only. |
| `backend/scripts/manual/` | Manual | Ad-hoc scripts that exercise a *running* server over HTTP. Not part of the automated test suite. |
| `docs/` | Docs | Deployment and design notes. |

## The three "app" folders

The repository root historically had three overlapping folders. This is what each one is:

- **`Janmitraapp/`** was not a mobile app. It was an older copy of the Django backend. It has been
  moved to `legacy/backend-snapshot-2026-04/`. `backend/` is the maintained tree (it has later
  migrations and is the only one referenced by Docker and the deploy scripts).

- **`janmitra_mobile/`** is the live Flutter application. The deploy scripts
  (`scripts/publish_webapp.sh`, `scripts/deploy_to_aws.ps1`) and the deployment docs all build from
  this path, and it is the most recently updated pointer.

- **`mobile/`** is the deprecated Flutter tree. Project notes mark it as "do not touch", and its
  pointer was last updated well before `janmitra_mobile/`.

### Caveat: the Flutter sources are not in this repository

`janmitra_mobile` and `mobile` are recorded in git as *gitlinks* (submodule pointers, mode
`160000`) but there is no `.gitmodules` file, so git does not know where to fetch them from. A
fresh clone therefore produces two empty directories:

| Path | Pinned commit |
|------|---------------|
| `janmitra_mobile` | `8082d6e46dd9f5f40e20aeacf7361953c68428e9` |
| `mobile` | `a3914e317c3a07a196a9a6859ec3c1b372227cef` |

To make the mobile app reproducible, either add a `.gitmodules` entry pointing at the Flutter
repository, or vendor the Flutter sources into this repository. Neither pointer has been changed
or removed here, because the mobile source could not be inspected from this repository alone.
