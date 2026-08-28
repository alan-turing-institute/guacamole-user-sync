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

**Note:** removing the `|| mv` fallback above was a *local, diagnostic-only*
step used to force `auditwheel`'s real error to the surface while
investigating — it was not kept. Subsequent manual testing of the Docker
build with the fallback removed surfaced a different, unrelated build
failure for another wheel in `requirements.txt`, indicating the fallback is
also relied on for a legitimate case (e.g. a wheel `auditwheel` correctly
declines to repair because it has nothing to repair) and not solely masking
this bug. The fix below therefore leaves the fallback in place; see
"Fix" (2) below.

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

### 2. Leave the `|| mv` fallback in place

Do **not** remove the `|| mv "${WHEEL}" /app/wheels/` fallback in the
`auditwheel repair` loop. It was suspected of being purely a bug (silently
masking the `patchelf` version conflict), but manual testing showed the
build depends on it for at least one other wheel that `auditwheel`
legitimately can't or doesn't need to repair — removing it breaks the build
in a different way than the one being fixed here. The `Dockerfile`'s repair
loop stays exactly as it currently is:

```dockerfile
RUN python -m pip wheel --no-cache-dir --no-binary :all: --wheel-dir /app/repairable -r requirements.txt && \
    for WHEEL in /app/repairable/*.whl; do \
        echo "\nRepairing ${WHEEL}" && \
        /root/.local/bin/auditwheel repair --wheel-dir /app/wheels --plat "manylinux_2_34_$(uname -m)" "${WHEEL}" || mv "${WHEEL}" /app/wheels/; \
    done && \
    rm -rf /app/repairable
```

Once `patchelf` is pinned to a compatible version (1, above), `auditwheel
repair` succeeds for `psycopg_c` on its own merits — the fallback is no
longer needed for *that* wheel — without having to touch or scope the
fallback itself. If a future need arises to make failures in this loop
loud again, that should be scoped per-dependency rather than applied as a
blanket change, and treated as a separate decision from this fix.

### 3. Verify

Rebuild and re-run the diagnosis's Step 1 and Step 2 checks:

```sh
docker build -t guacamole-user-sync:fixed .
docker run --rm --entrypoint python guacamole-user-sync:fixed -c "import psycopg; print(psycopg.__version__)"
```

This should succeed with no `libpq.so.5` error. Confirm the shipped wheel is
now the repaired, `manylinux`-tagged one (diagnosis Step 2), and that
`synchronise.py` still starts correctly against a real PostgreSQL instance.

## Update: pinning `patchelf` via `pipx` was not sufficient

Applying the fix above and rebuilding produced a *different* failure at the
same `auditwheel repair` step, for every wheel in the loop:

```
ValueError: Cannot find required utility `patchelf` in PATH
```

This is not a version problem — `patchelf==0.17.2.2` did install
successfully via `pipx`. It's a **`PATH` problem**: `pipx install` places
its symlinked executables in `~/.local/bin` (`/root/.local/bin` for the
`root` user the builder stage runs as), and prints its own warning to that
effect during install:

```
⚠️  Note: '/root/.local/bin' is not on your PATH environment variable. ...
    Run `pipx ensurepath` to automatically add it, or manually modify your
    PATH in your shell's config file (i.e. ~/.bashrc).
```

That warning was already visible in the build log before this update, but
went unnoticed because the Dockerfile invokes `auditwheel` and `hatch` by
their **absolute path** (`/root/.local/bin/auditwheel`, `/root/.local/bin/hatch`),
which sidesteps needing `/root/.local/bin` on `PATH` to *launch* those
tools. `patchelf` is different: `auditwheel` doesn't get handed
`patchelf`'s path directly — it shells out to a bare `patchelf` command
and locates it itself via `shutil.which()` against the `PATH` environment
variable of the `RUN` step. A Docker `RUN` layer has no shell profile
(`~/.bashrc`, etc.) sourced, and `pipx ensurepath` only ever edits shell
profile files, not the image's `ENV`, so nothing in the current Dockerfile
ever adds `/root/.local/bin` to `PATH` — `patchelf` stays installed but
unreachable by anything doing a `PATH` lookup, `auditwheel` included.

Reproduced directly (`python:3.11.9-slim`, matching the builder base):

```sh
$ ls -la /root/.local/bin/
lrwxrwxrwx 1 root root 49 auditwheel -> /root/.local/pipx/venvs/auditwheel/bin/auditwheel
lrwxrwxrwx 1 root root 45 patchelf   -> /root/.local/pipx/venvs/patchelf/bin/patchelf
$ echo $PATH
/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin   # no /root/.local/bin
$ /root/.local/bin/auditwheel repair --wheel-dir /tmp/repaired \
      --plat manylinux_2_34_x86_64 psycopg_c-3.2.3-cp311-cp311-linux_x86_64.whl
ValueError: Cannot find required utility `patchelf` in PATH
```

Re-running the same repair with `/root/.local/bin` prepended to `PATH`
succeeds and produces the expected `manylinux`-retagged wheel — confirming
`PATH` visibility, not the `patchelf` version, is the remaining blocker.

### Updated fix

Add `/root/.local/bin` to `PATH` for the rest of the `builder` stage,
right after the `pipx install` loop, instead of relying on invoking each
tool by absolute path:

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

ENV PATH="/root/.local/bin:${PATH}"
```

With `PATH` updated at the image-layer level (`ENV`, not a shell rc file),
every subsequent `RUN` step in the `builder` stage inherits it — including
the `auditwheel repair` subprocess's own internal `patchelf` lookup. The
existing absolute-path invocations (`/root/.local/bin/hatch`,
`/root/.local/bin/auditwheel`) can be simplified to just `hatch` and
`auditwheel` once `PATH` covers them, but that simplification is cosmetic
and not required for the fix — leaving them as absolute paths is harmless
now that `PATH` also resolves them correctly.

### Verify

Same as "Verify" above (Step 3), plus confirming the build log no longer
shows `ValueError: Cannot find required utility` for any wheel in the
repair loop, and that `psycopg_c`'s shipped wheel is `manylinux`-tagged
(diagnosis Step 2).

## CI: out of scope for this fix

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
or already tagged and pushed to `ghcr.io` — exactly what happened here. That
gap still exists after this fix.

**This fix does not change any GitHub Actions workflow.** `publish_docker.yaml`
is left exactly as it is, and no new build-verification workflow is added.
Splitting build/publish into separate workflows, or otherwise gating PRs on
a Docker build, is a reasonable idea for closing this gap, but it's a
separate decision from fixing the `patchelf`/`auditwheel` conflict and is
not part of this change.
