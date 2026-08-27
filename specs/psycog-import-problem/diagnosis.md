# Diagnosis: `psycopg` "c" implementation fails to import at runtime

## Symptom

Running the published container and executing `import psycopg` fails with:

```
couldn't import psycopg 'c' implementation: libpq.so.5: cannot open shared object file: No such file or directory
```

## Where this comes from

The `Dockerfile` builds `psycopg[c]` (not `psycopg[binary]`) from source in the
`builder` stage, then tries to make the resulting wheel self-contained via
`auditwheel repair`, so it can run in the `gcr.io/distroless/python3-debian12:debug`
final stage — an image with no package manager, so there is no way to
`apt-get install libpq5` there after the fact.

Relevant lines:

```dockerfile
## Install build prerequisites
RUN apt-get update && \
    apt-get install -y \
        dumb-init \
        g++ \
        gcc \
        libpq-dev \
        ...

## Build wheels for dependencies using auditwheel to include shared libraries
RUN python -m pip wheel --no-cache-dir --no-binary :all: --wheel-dir /app/repairable -r requirements.txt && \
    for WHEEL in /app/repairable/*.whl; do \
        echo "\nRepairing ${WHEEL}" && \
        /root/.local/bin/auditwheel repair --wheel-dir /app/wheels --plat "manylinux_2_34_$(uname -m)" "${WHEEL}" || mv "${WHEEL}" /app/wheels/; \
    done && \
    rm -rf /app/repairable
```

`psycopg[c]`'s C extension links dynamically against `libpq.so.5`
(provided by `libpq-dev`, via `libpq5`, in the builder stage only). The
intent of `auditwheel repair` is to detect that dependency, vendor a copy
of `libpq.so.5` (and its own transitive deps: `libssl`, `libcrypto`,
`libgssapi_krb5`, etc.) inside the wheel under a `<pkg>.libs/` directory,
and rewrite the extension's RPATH to point at the vendored copy — the
standard "manylinux self-contained wheel" pattern.

**The bug is the `|| mv "${WHEEL}" /app/wheels/` fallback.** If
`auditwheel repair` fails or declines to repair the `psycopg` wheel for
any reason (e.g. it can't satisfy the requested `manylinux_2_34` platform
tag for one of `libpq.so.5`'s own transitive shared-library dependencies,
or the produced wheel would depend on symbol versions outside the policy),
the build does **not** fail — it silently falls back to shipping the
**unrepaired** wheel, which still declares a dynamic dependency on
`libpq.so.5` but does not bundle it. That wheel installs fine in the final
distroless image (`pip install` doesn't check shared-library
resolvability), and the failure only surfaces later, at `import psycopg`
time, when the dynamic loader can't find `libpq.so.5` anywhere in the
distroless image's library search path.

This matches the project's own git history — `d05803c :bug: Ensure that
auditwheel builds correct wheel for the build-platform being used` shows
`auditwheel`'s behaviour here has already been a source of build-platform
mismatches, so a further edge case slipping through is plausible.

## How to confirm

Before applying a fix, confirm the failure mode with the following
sequence. Run these from the repo root; they don't require changing the
`Dockerfile` (the builder stage is targeted directly with `--target`).

### Step 1 — Reproduce the runtime failure

```sh
docker build -t guacamole-user-sync:diag .
docker run --rm --entrypoint python guacamole-user-sync:diag -c "import psycopg"
```

Expected output (confirms the reported symptom before digging further):

```
couldn't import psycopg 'c' implementation: libpq.so.5: cannot open shared object file: No such file or directory
```

### Step 2 — Inspect which wheel actually shipped

Build only the `builder` stage and open a shell in it, so `/app/wheels`
can be inspected directly:

```sh
docker build --target builder -t guacamole-user-sync:builder .
docker run --rm -it guacamole-user-sync:builder bash
```

Inside that container:

```sh
ls -la /app/wheels/ | grep -i psycopg
```

- **Repaired** wheel: filename is retagged to the requested platform, e.g.
  `psycopg_c-3.2.3-cp311-cp311-manylinux_2_34_x86_64.whl`.
- **Unrepaired** (fallback) wheel: keeps whatever tag `pip wheel` produced
  before repair, e.g. `psycopg_c-3.2.3-cp311-cp311-linux_x86_64.whl` —
  note `linux_x86_64` instead of `manylinux_2_34_x86_64`. This filename
  difference alone is enough to confirm the fallback path was taken.

Confirm by unzipping it:

```sh
cd /tmp
python -m zipfile -l /app/wheels/psycopg_c-*.whl
```

- Repaired wheel: listing includes a `psycopg_c.libs/` directory
  containing a vendored `libpq-<hash>.so.5` (plus `libssl`, `libcrypto`,
  `libgssapi_krb5`, etc.).
- Unrepaired wheel: no `.libs/` directory anywhere in the listing.

### Step 3 — Get `auditwheel`'s real error by running it outside the `||` fallback

Still inside the `builder`-stage container from Step 2, locate the
pre-repair wheel and re-run `auditwheel repair` directly, without the
`|| mv ...` fallback masking its exit code:

```sh
# Rebuild the raw (non-repaired) wheel into a scratch dir, mirroring the Dockerfile step
mkdir -p /tmp/repairable
python -m pip wheel --no-cache-dir --no-binary :all: --wheel-dir /tmp/repairable psycopg[c]==3.2.3

# Run auditwheel directly and capture its actual diagnosis
/root/.local/bin/auditwheel show /tmp/repairable/psycopg_c-*.whl
/root/.local/bin/auditwheel repair --wheel-dir /tmp/repaired --plat manylinux_2_34_$(uname -m) /tmp/repairable/psycopg_c-*.whl
echo "exit code: $?"
```

`auditwheel show` reports which shared libraries the wheel depends on and
which of those it considers policy-compliant vs. not; `auditwheel repair`'s
stderr states the specific reason for refusal if it fails (common ones:
a dependency requires a newer `GLIBC`/symbol version than the target
`manylinux_2_34` policy allows, or a library it depends on is itself
excluded from the policy's allowed list). A non-zero exit code here,
paired with the `linux_x86_64`-tagged (not `manylinux`-tagged) wheel
found in Step 2, confirms the `|| mv` fallback in the `Dockerfile` is
what's shipping the broken wheel.

### Step 4 — Confirm no other copy of `libpq.so.5` reaches the final image

```sh
docker run --rm --entrypoint /busybox/sh guacamole-user-sync:diag -c "find / -xdev -name 'libpq.so.5*' 2>/dev/null"
```

Expected output: empty — confirming the final distroless image has no
copy of `libpq.so.5` anywhere (neither system-installed, since there's no
package manager, nor vendored, since Step 2/3 showed the shipped wheel
wasn't repaired), which is the direct cause of the `ImportError` in Step 1.

## Candidate fixes

### Option A — Fail the build loudly instead of silently falling back (diagnostic-only)

Remove the `|| mv ... ` fallback for `psycopg`'s wheel specifically (or for
all wheels) so a repair failure breaks the Docker build with `auditwheel`'s
real error message, instead of producing a container that fails at
runtime. This doesn't fix the underlying issue by itself, but turns a
runtime failure into a build-time failure with an actionable error, and is
a prerequisite for diagnosing *why* `auditwheel` is rejecting the wheel
(see "How to confirm" above).

### Option B — Switch to `psycopg[binary]` for the runtime dependency

Instead of compiling `psycopg[c]` from source and relying on `auditwheel`
to bundle `libpq`, depend on the official `psycopg-binary` wheels published
to PyPI. Those wheels already vendor a statically-linked/self-contained
`libpq` (and OpenSSL) built by the psycopg maintainers for `manylinux`, so
no local compilation or `auditwheel` repair step is needed at all. This
removes the biggest source of build fragility (`gcc`/`g++`/`libpq-dev`/
`auditwheel` in the builder stage) at the cost of moving off the
project's stated "self-built wheel" approach, and pinning to whatever
`libpq`/OpenSSL versions psycopg's maintainers ship in `psycopg-binary`
rather than the ones in `python:3.11.9-slim`.

### Option C — Explicitly vendor `libpq.so.5` (and its deps) into the final image

Keep `psycopg[c]`, but stop relying solely on `auditwheel` to make it
self-contained: explicitly `COPY --from=builder` the runtime shared
libraries (`libpq.so.5`, `libssl.so.*`, `libcrypto.so.*`,
`libgssapi_krb5.so.*`, etc., discoverable via `ldd` on the compiled
extension in the builder stage) into a library directory in the final
image, and set `LD_LIBRARY_PATH` (or bake an `ld.so.conf` equivalent, though
distroless has no `ldconfig`) to include it. More manual than Option A/B,
but keeps the current "compile from source" approach and doesn't depend on
`auditwheel` succeeding.

### Recommendation

Start with **Option A** to get a real error message from `auditwheel`
during the build — that tells us definitively *why* the psycopg wheel
isn't being repaired, and determines whether **Option B** (simpler,
recommended if the underlying cause is a genuine `auditwheel`/manylinux
policy limitation) or **Option C** (if we need to keep building from
source for some reason, e.g. compiling against a specific `libpq` version)
is the right long-term fix.

## Suggested next steps

1. Apply Option A locally, rebuild the Docker image, and capture
   `auditwheel`'s actual failure output for the `psycopg_c` wheel.
2. Based on that output, decide between Option B and Option C.
3. Rebuild and verify with a container smoke test: run the final image and
   confirm `python -c "import psycopg"` succeeds without the `libpq.so.5`
   error, both directly and via `synchronise.py`'s normal startup path
   (which needs a working PostgreSQL connection).
4. Add this check (or an equivalent) to CI so a future regression in the
   `auditwheel`/wheel-bundling step is caught at build time rather than at
   deploy time.
