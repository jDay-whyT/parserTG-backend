FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
ENV PYTHONPATH=/app

# System deps for Chromium (CloakBrowser) + build tools
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc g++ python3-dev build-essential libpq-dev pkg-config \
        libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
        libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
        libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 \
        libpangocairo-1.0-0 libpango-1.0-0 libcairo2 \
        libglib2.0-0 libx11-6 libxcb1 libxext6 libxshmfence1 \
        fonts-noto-color-emoji fonts-freefont-ttf \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install -U pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# Install CloakBrowser + pre-download stealth Chromium binary (~200MB, cached in image)
RUN pip install --no-cache-dir cloakbrowser \
    && python -m cloakbrowser install

COPY shared ./shared
COPY services ./services

CMD ["python", "-m", "services.ingest.main"]
