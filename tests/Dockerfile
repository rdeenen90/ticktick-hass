# Test image: Home Assistant's test harness plus this repo's test requirements.
FROM python:3.14-slim
WORKDIR /app
COPY requirements_test.txt .
RUN pip install --no-cache-dir -r requirements_test.txt
CMD ["pytest"]
