# Build working image
FROM python:3.12.5-slim AS builder

## Set up work directory
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

## Install prerequisites
RUN apt-get update && \
    apt-get install -y \
        dumb-init \
        gcc \
        libldap2-dev \
        libsasl2-dev \
        pipx \
        && \
    pipx install hatch

## Use hatch to determine dependencies
COPY README.md pyproject.toml ./
COPY guacamole_user_sync guacamole_user_sync
RUN /root/.local/bin/hatch run pip freeze > requirements.txt

## Build wheels for dependencies
RUN python -m pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# Build final image
FROM python:3.12.5-slim

## Set up work directory
WORKDIR /app

## Copy required files
COPY --from=builder /app/wheels /tmp/wheels
COPY --from=builder /app/requirements.txt .
COPY --from=builder /usr/lib/aarch64-linux-gnu/libldap* /usr/lib/aarch64-linux-gnu/liblber* /usr/lib/aarch64-linux-gnu/libsasl2* /usr/lib/aarch64-linux-gnu/
COPY --from=builder /usr/bin/dumb-init /usr/bin/dumb-init
COPY guacamole_user_sync guacamole_user_sync
COPY synchronise.py .

## Install Python packages
RUN python -m pip install --no-cache /tmp/wheels/* && rm -rf /tmp/wheels

## Set file permissions
RUN chmod 0700 /app/synchronise.py

## Run jobs with dumb-init
ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["python", "/app/synchronise.py"]