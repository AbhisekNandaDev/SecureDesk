# Multi-stage build for PostgreSQL with pgvector extension
ARG PG_VERSION=16
FROM postgres:${PG_VERSION}-bookworm AS builder

ARG PG_VERSION=16
ARG PGVECTOR_VERSION=v0.8.0

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    postgresql-server-dev-${PG_VERSION} \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Clone and compile pgvector from source
WORKDIR /tmp/pgvector
RUN git clone --branch ${PGVECTOR_VERSION} https://github.com/pgvector/pgvector.git . \
    && make clean \
    && make OPTFLAGS="" \
    && make install

# Final minimal PostgreSQL image
FROM postgres:${PG_VERSION}-bookworm

ARG PG_VERSION=16

# Copy compiled extension libraries and metadata from builder
COPY --from=builder /usr/lib/postgresql/${PG_VERSION}/lib/vector.so /usr/lib/postgresql/${PG_VERSION}/lib/
COPY --from=builder /usr/share/postgresql/${PG_VERSION}/extension/vector* /usr/share/postgresql/${PG_VERSION}/extension/

# Copy initialization script to automatically enable the vector extension
COPY init.sql /docker-entrypoint-initdb.d/01-init-vector.sql

# Expose standard PostgreSQL port
EXPOSE 5432

