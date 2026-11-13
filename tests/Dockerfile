# Test image: Home Assistant's test harness plus this repo's test requirements.
FROM python:3.14-slim
# Home Assistant builds a few of its runtime packages from source and calls
# ffmpeg; only scripts/develop.sh needs these, the tests do not.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential ffmpeg \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements_test.txt .
RUN pip install --no-cache-dir -r requirements_test.txt
CMD ["pytest"]
