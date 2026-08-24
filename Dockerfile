# ── Stage 1: dependency install ───────────────────────────────────────────────
FROM python:3.12-slim AS deps

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt


# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Non-root user for security
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

# Copy installed packages from the build stage
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

COPY server/ ./server/
COPY tools/ ./tools/
COPY resources/ ./resources/
COPY prompts/ ./prompts/
COPY utils/ ./utils/
COPY main.py .

# Cloud Run injects PORT; MCP_TRANSPORT switches from stdio → sse
ENV MCP_TRANSPORT=sse
ENV PORT=8080
ENV AWS_DEFAULT_REGION=us-east-1
# Credentials — supply at deploy time via --set-env-vars or Secret Manager:
#   AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, (AWS_SESSION_TOKEN)

EXPOSE 8080

USER appuser

# Healthcheck — Cloud Run will mark the container healthy when /sse 200s
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/sse')" || exit 1

CMD ["python", "main.py"]
