# Solution: `psycopg` "c" implementation fails to import at runtime

This builds on [diagnosis.md](./diagnosis.md). Following the diagnosis's
"How to confirm" steps and applying **Option A** (removing the `|| mv`
fallback so `auditwheel`'s real error surfaces) produced:

```
ValueError: patchelf 0.14.3 found. auditwheel repair requires patchelf >= 0.14.5.
```

This confirms the diagnosis's suspicion at `d05803c` was on the right track,
but the actual root cause is narrower than Options B/C in the diagnosis
assumed: it is not a genuine `manylinux_2_34` policy incompatibility with
`libpq.so.5`'s transitive dependencies. It's a **version conflict between two
independently-sourced build tools**, so `auditwheel repair` never even gets
to the point of evaluating policy compliance — it fails immediately on
startup, for every wheel it's asked to repair.

## Root cause

The `builder` stage installs `auditwheel` and `patchelf` from two different
package sources with no version pinning between them:

```dockerfile
RUN apt-get update && \
    apt-get install -y \
        ...
        patchelf \
        pipx \
        ...
        && \
    for EXECUTABLE in \
        "auditwheel" \
        "hatch"; \
        do pipx install "$EXECUTABLE"; \
    done
```

- `patchelf` comes from **Debian's apt repository** (`python:3.11.9-slim` is
  Debian bookworm), which provides **0.14.3**.
- `auditwheel` comes from **PyPI via `pipx install auditwheel`**, unpinned —
  so it always resolves to the latest release, which requires
  **`patchelf >= 0.14.5`**.

`auditwheel` calls out to the `patchelf` binary on `PATH` as a subprocess; it
checks the version on startup and raises `ValueError` if it's too old.
Because apt's `patchelf` is capped by whatever Debian bookworm shipped
(0.14.3) and is never updated by anything in the Dockerfile, this check
fails for *every* wheel `auditwheel repair` is asked to process, including
`psycopg_c`.

The `|| mv "${WHEEL}" /app/wheels/` fallback (see diagnosis) then silently
swallows this immediate, unconditional failure and ships the unrepaired
wheel instead — which is why the diagnosis's Step 2/3 saw an
un-manylinux-tagged, unrepaired `psycopg_c` wheel with no vendored
`libpq.so.5`, leading to the `ImportError` at container runtime.

This also means the bug isn't specific to `psycopg` — every wheel repaired
in that loop is silently going unrepaired. `psycopg` is simply the only one
whose absence of repair is *observable*, because it's the only dependency
with a hard runtime link to a native shared library (`libpq.so.5`) that
distroless has no other way to provide.

## Fix

### 1. Install a `patchelf` that satisfies `auditwheel`'s requirement

Stop taking `patchelf` from apt (tied to the Debian release and outside our
control) and install it the same way as `auditwheel` — via `pipx`, from
PyPI, where the `patchelf` package ships a current prebuilt binary:

```dockerfile
RUN apt-get update && \
    apt-get install -y \
        dumb-init \
        g++ \
        gcc \
        libpq-dev \
        pipx \
        python3-dev \
        && \
    for EXECUTABLE in \
        "auditwheel==6.3.0" \
        "hatch" \
        "patchelf==0.17.2.2"; \
        do pipx install "$EXECUTABLE"; \
    done
```

- Drop `patchelf` from the `apt-get install` line entirely.
- Add `"patchelf==0.17.2.2"` (or whatever current release satisfies
  `>= 0.14.5`) to the `pipx install` loop, alongside `auditwheel`.
- Pin **both** `auditwheel` and `patchelf` to explicit versions instead of
  leaving them unpinned. This is the actual fix for reproducibility: an
  unpinned `pipx install auditwheel` picking up a newer release with a
  higher `patchelf` floor is exactly how this broke, and it can silently
  break again the same way with a different version pair.

`pipx install` puts `~/.local/bin` on `PATH` ahead of `/usr/bin`, so the
pipx-installed `patchelf` shadows any system one — no other Dockerfile
changes are needed for `auditwheel` to find it.

### 2. Keep Option A (fail loud) as a permanent safeguard, not just a diagnostic step

Even with (1) fixed, keep the `|| mv` fallback removed (or gated) so a
*future* tool incompatibility fails the Docker build immediately instead of
producing a container that only fails at runtime:

```dockerfile
RUN python -m pip wheel --no-cache-dir --no-binary :all: --wheel-dir /app/repairable -r requirements.txt && \
    for WHEEL in /app/repairable/*.whl; do \
        echo "\nRepairing ${WHEEL}" && \
        /root/.local/bin/auditwheel repair --wheel-dir /app/wheels --plat "manylinux_2_34_$(uname -m)" "${WHEEL}"; \
    done && \
    rm -rf /app/repairable
```

If a *legitimate* manylinux-policy failure ever needs the fallback for some
specific dependency (i.e. a wheel that genuinely can't be repaired and
doesn't need to be, e.g. a pure-Python wheel `auditwheel` declines to touch),
scope the fallback to that dependency by name rather than swallowing errors
for the whole loop — don't reintroduce a blanket `|| mv`.

### 3. Verify

Rebuild and re-run the diagnosis's Step 1 and Step 2 checks:

```sh
docker build -t guacamole-user-sync:fixed .
docker run --rm --entrypoint python guacamole-user-sync:fixed -c "import psycopg; print(psycopg.__version__)"
```

This should succeed with no `libpq.so.5` error. Confirm the shipped wheel is
now the repaired, `manylinux`-tagged one (diagnosis Step 2), and that
`synchronise.py` still starts correctly against a real PostgreSQL instance.

## Preventing a recurrence: catch this in CI, not in production

The reason this shipped is that **nothing in CI ever builds or runs the
Docker image**. Looking at the existing workflows:

- `test_code.yaml` / `lint_code.yaml` run on every PR and push to `main`,
  but only exercise `hatch run test:all` / `hatch run lint:all` — pure
  Python, no Docker involved.
- `publish_docker.yaml` is the *only* workflow that builds the image, and it
  only triggers `on: push: branches: [main]` / `tags: [v*]` — i.e. **after**
  a PR is merged, or on a release tag. There is no workflow that builds the
  image on a PR.

So a build-time regression like this one (or a runtime regression like the
resulting `ImportError`) is only ever discovered once it's already on `main`
or already tagged and pushed to `ghcr.io` — exactly what happened here.

Recommended CI changes:

1. **Build the Docker image on every PR**, not just on push to `main`.
   Add a `pull_request` trigger (mirroring `test_code.yaml`/
   `lint_code.yaml`) to a Docker build workflow, using
   `docker/build-push-action@v6` with `push: false` so it builds without
   publishing:

   ```yaml
   on:
     pull_request:
   jobs:
     build_image:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: docker/build-push-action@v6
           with:
             push: false
             load: true
             tags: guacamole-user-sync:ci
   ```

   This alone would have caught the `auditwheel`/`patchelf` failure at PR
   time, once the `|| mv` fallback in fix (2) above is in place — the build
   itself now fails on the real error instead of completing silently.

2. **Add a smoke test step after the build** that actually runs the image
   and imports `psycopg`, so a *runtime* regression (like the original
   silent fallback, before the build-time fix) is caught even if the build
   itself succeeds:

   ```yaml
         - name: Smoke test the image
           run: |
             docker run --rm --entrypoint python guacamole-user-sync:ci \
               -c "import psycopg"
   ```

   This is cheap (no PostgreSQL/LDAP server needed) and would have caught
   this exact bug directly, independent of whether the `auditwheel` failure
   is made loud or not.

3. Either fold these into `publish_docker.yaml` (build+smoke-test on PRs,
   build+smoke-test+push on `main`/tags) or split into a separate
   `build_docker.yaml` that runs on PRs only, with `publish_docker.yaml`
   left as-is for the actual publish step. Splitting is preferable so a
   transient registry/login issue in the publish job never blocks PR
   feedback, and vice versa.
