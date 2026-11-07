FROM node:24-bookworm@sha256:64af3819f9275802414d7cdc38c27e9d82bd564dec4d4da87d008255d36c63b4 AS frontend
WORKDIR /frontend
COPY seed/frontend/procurement-ontology/ ./
RUN npm ci --ignore-scripts && npm run build

FROM python:3.11-slim@sha256:e88e9763f943ec1834f992a4b51e0f24500486803e8bc534e5767af9ea65f6ce
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/* && pip install --no-cache-dir uv==0.12.20
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_PYTHON_DOWNLOADS=never \
    PATH=/opt/venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 LITELLM_LOCAL_MODEL_COST_MAP=True
WORKDIR /opt/ontology-seed
COPY seed/ ./
RUN uv sync --locked --no-dev --no-editable --project services/procurement_ontology
COPY --from=frontend /frontend/dist ./frontend/procurement-ontology/dist
COPY entrypoint.py /usr/local/bin/ontology-entrypoint.py
ARG ONTOLOGY_RELEASE
ARG ONTOLOGY_REVISION
ARG ONTOLOGY_VERSION
LABEL org.opencontainers.image.revision=$ONTOLOGY_REVISION \
      org.opencontainers.image.version=$ONTOLOGY_VERSION \
      io.yunhezhiyuan.source-content=$ONTOLOGY_RELEASE
RUN test "$(cat VERSION)" = "$ONTOLOGY_VERSION"
RUN python /usr/local/bin/ontology-entrypoint.py --write-manifest "$ONTOLOGY_RELEASE" \
    && useradd --uid 1000 --create-home ontology
USER 1000:1000
ENV PROCUREMENT_RUNTIME_DIR=/runtime PROCUREMENT_DRAFT_PARENT=/workspace/drafts
EXPOSE 8002
ENTRYPOINT ["python", "/usr/local/bin/ontology-entrypoint.py"]
CMD ["serve", "--port", "8002"]
