# ---- Backend Stage ----
FROM python:3.12-slim AS backend

WORKDIR /app/backend

# Detect architecture and install Stockfish accordingly
ARG TARGETARCH
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    wget \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY backend/ .

# Install Stockfish: apt for ARM64, download binary for x86_64
RUN mkdir -p uploads data stockfish/stockfish \
    && if [ "$TARGETARCH" = "arm64" ]; then \
        echo "ARM64 detected - installing Stockfish via apt..." \
        && apt-get update \
        && apt-get install -y --no-install-recommends stockfish \
        && STOCKFISH_BIN=$(which stockfish || echo "") \
        && if [ -n "$STOCKFISH_BIN" ]; then \
            cp "$STOCKFISH_BIN" stockfish/stockfish/stockfish-arm64 \
            && chmod +x stockfish/stockfish/stockfish-arm64 \
            && echo "Stockfish (apt) installed at: $STOCKFISH_BIN"; \
        else \
            echo "WARNING: apt stockfish not found"; \
        fi \
        && rm -rf /var/lib/apt/lists/*; \
    else \
        echo "x86_64 detected - downloading Stockfish binary..." \
        && wget -q "https://github.com/official-stockfish/Stockfish/releases/download/sf_17.1/stockfish-ubuntu-x86-64-avx2.tar" -O /tmp/stockfish.tar \
        && tar -xf /tmp/stockfish.tar -C /tmp \
        && cp /tmp/stockfish/stockfish-ubuntu-x86-64-avx2 stockfish/stockfish/stockfish-ubuntu-x86-64-avx2 \
        && chmod +x stockfish/stockfish/stockfish-ubuntu-x86-64-avx2 \
        && rm -rf /tmp/stockfish* \
        && echo "Stockfish (binary) downloaded successfully"; \
    fi \
    || echo "WARNING: Stockfish install failed - analysis will run in mock mode"

# Verify Stockfish binary exists
RUN ls -la stockfish/stockfish/ && echo "Stockfish binary verified"

EXPOSE 5000

# 1 worker + 1 Stockfish fits in 512MB; --preload shares initialization
# --timeout 300 for long analysis jobs
CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:5000", "--timeout", "300", "--preload", "run:app"]


# ---- Frontend Build Stage ----
FROM node:18-alpine AS frontend-build

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

COPY frontend/ .
RUN npm run build


# ---- Production Stage (Nginx + Frontend) ----
FROM nginx:alpine AS production

COPY --from=frontend-build /app/frontend/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
