# ===================
# Build working image
# ===================
FROM python:3.11.9-slim AS builder

## Set up work directory
WORKDIR /app

## Configure Python settings
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

## Install build prerequisites
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get install -y \
        dumb-init \
        g++ \
        gcc \
        libpq-dev \
        patchelf \
        pipx \
        python3-dev \
        && \
    for EXECUTABLE in \
        "auditwheel" \
        "hatch"; \
        do pipx install "$EXECUTABLE"; \
    done

## Copy project files needed by hatch
COPY README.md pyproject.toml ./
COPY guacamole_user_sync guacamole_user_sync

## Build a separate pip wheel which can be used to install itself
## N.B. we rename the wheel so that we can refer to it by name later
RUN python -m pip wheel --no-cache-dir --wheel-dir /app/wheels pip && \
    mv /app/wheels/pip*whl /app/wheels/pip-0-py3-none-any.whl

## Build wheels for dependencies then use auditwheel to include shared libraries
## Note that we need to specify psycopg[c] in order to ensure that dependencies are included in the wheel
RUN /root/.local/bin/hatch run pip freeze | grep -v "^-e" > requirements.txt && \
    sed -i "s/psycopg=/psycopg[c]=/g" requirements.txt && \
    python -m pip wheel --no-cache-dir --no-binary :all: --wheel-dir /app/repairable -r requirements.txt && \
    for WHEEL in /app/repairable/*.whl; do \
        echo "\nRepairing ${WHEEL}" && \
        /root/.local/bin/auditwheel repair --wheel-dir /app/wheels --plat "manylinux_2_34_$(uname -m)" "${WHEEL}" || mv "${WHEEL}" /app/wheels/; \
    done && \
    rm -rf /app/repairable

## Build a separate wheel for the project
RUN /root/.local/bin/hatch build -t wheel && \
    mv dist/guacamole_user_sync*.whl /app/wheels/ && \
    echo "guacamole-user-sync>=0.0" >> requirements.txt


# =================
# Build final image
# =================
FROM gcr.io/distroless/python3-debian12:debug

## This shell is only available in the debug image
SHELL ["/busybox/sh", "-c"]

## Set up work directory
WORKDIR /app

## Configure Python settings
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

## Copy required files
COPY --from=builder /app/wheels /tmp/wheels
COPY --from=builder /app/requirements.txt .
COPY --from=builder /usr/bin/dumb-init /usr/bin/dumb-init
COPY synchronise.py .

## Install pip from wheel
RUN python /tmp/wheels/pip-0-py3-none-any.whl/pip install \
    --break-system-packages \
    --root-user-action ignore \
    --no-index \
    /tmp/wheels/pip-0-py3-none-any.whl && \
    rm /tmp/wheels/pip-0-py3-none-any.whl

## Install Python packages from wheels
RUN python -m pip install \
        --break-system-packages \
        --root-user-action ignore \
        --find-links /tmp/wheels/ \
        -r /app/requirements.txt && \
    rm -rf /tmp/wheels && \
    python -m pip freeze

## Set file permissions
RUN chmod 0700 /app/synchronise.py

## Run jobs with dumb-init
ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["python", "/app/synchronise.py"]
