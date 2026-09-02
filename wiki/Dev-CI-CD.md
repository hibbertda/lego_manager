# Dev: CI/CD

This project's code lives on a self-hosted Gitea instance (primary) and is
also mirrored to a public GitHub repo. Each remote has its own, fully
independent CI workflow — they don't trigger each other and publish to
different registries.

## Gitea Actions (primary)

`.gitea/workflows/build-image.yml` builds the Docker image on the
in-cluster Gitea Actions runner and pushes it to the Gitea container
registry as `gitea.thehibbs.net/xamlok/lego_manager`, tagged both `latest`
(or a manually-chosen tag) and the short commit SHA. It runs automatically
on every push to `main`, or on demand via Actions -> "Build lego-manager
image" -> "Run workflow".

One-time setup required in the Gitea repo:

- Generate a Personal Access Token (Settings -> Applications) with
  `write:package` and `read:package` scopes — the built-in Actions token
  doesn't have registry write access.
- Add it as a repo secret named `DOCKERBUILD_SECRET` (Repo -> Settings ->
  Actions -> Secrets).

## GitHub Actions (public mirror)

`.github/workflows/build-release.yml` builds the same Dockerfile on GitHub's
own runners, pushes it to the GitHub Container Registry
(`ghcr.io/<owner>/lego_manager`) tagged `latest` and an auto-generated
version (`v1.0.<run number>`, or a custom tag via manual dispatch), then
creates a GitHub Release for that tag with auto-generated release notes. It
runs automatically on every push to `main` on GitHub, or on demand via
Actions -> "Build and release container" -> "Run workflow".

No secrets to configure — it authenticates to `ghcr.io` with the
auto-provisioned `GITHUB_TOKEN` (needs `contents: write` + `packages: write`
permissions, already set in the workflow). The one manual step is making the
package public after its first run: `github.com/users/<owner>/packages` ->
`lego_manager` -> Package settings -> Change visibility (new GHCR packages
default to private even in a public repo).

## Redeploying after a new image is published

Running deployments need to be restarted to pull the new image (mutable
tags aren't automatically re-pulled):

```bash
# Kubernetes
kubectl -n lego-manager rollout restart deploy/lego-manager

# docker compose
docker compose -f docker-compose.registry.yml pull
docker compose -f docker-compose.registry.yml up -d
```

See [Installation](Installation.md) for the full deployment/upgrade
workflow.
