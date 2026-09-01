# Dev: CI/CD

`.gitea/workflows/build-image.yml` builds the Docker image on the
in-cluster Gitea Actions runner and pushes it to the Gitea container
registry as `gitea.thehibbs.net/xamlok/lego_manager`, tagged both `latest`
(or a manually-chosen tag) and the short commit SHA. It runs automatically
on every push to `main`, or on demand via Actions -> "Build lego-manager
image" -> "Run workflow".

## One-time setup required in the Gitea repo

- Generate a Personal Access Token (Settings -> Applications) with
  `write:package` and `read:package` scopes — the built-in Actions token
  doesn't have registry write access.
- Add it as a repo secret named `DOCKERBUILD_SECRET` (Repo -> Settings ->
  Actions -> Secrets).

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
