FROM debian:stable-slim

# Set up work directory
WORKDIR /app

# Install prerequisites
RUN apt-get update -y; \
    apt upgrade -y; \
    apt install -y \
        cron \
        gcc \
        libpq-dev \
        make \
        postgresql-client \
        ruby \
        ruby-dev \
        s6;

# Install ruby requirements
RUN gem install mustache pg-ldap-sync;

# Copy required files
COPY resources resources
COPY scripts scripts
COPY templates templates
COPY synchronise /etc/s6/synchronise

# Set file permissions
RUN chmod 0700 /etc/s6/synchronise/* /app/scripts/*
RUN chmod 0600 /app/resources/* /app/templates/*

# Schedule jobs with s6
CMD ["/bin/s6-svscan", "/etc/s6"]