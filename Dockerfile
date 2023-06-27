FROM debian:stable-slim

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
        ruby-dev;

# Install ruby requirements
RUN gem install mustache pg-ldap-sync;

# Copy required files
COPY templates templates
COPY scripts scripts
COPY run.sh .

# Add a cron job to run the main program every minute, redirecting output
RUN crontab -l | { echo "*/1 * * * * /app/run.sh > /proc/1/fd/1 2>/proc/1/fd/2"; } | crontab -;

# Run cron in the foreground
CMD ["cron", "-f"]
