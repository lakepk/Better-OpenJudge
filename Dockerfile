FROM python:3.11-slim

# g++ is required by the judge engine to compile C++ submissions
RUN apt-get update \
    && apt-get install -y --no-install-recommends g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock

COPY . .

# Separate directory for the SQLite database (mounted as volume)
RUN mkdir -p /app/db

EXPOSE 4399
ENV PYTHONUNBUFFERED=1
ENV DATABASE_PATH=/app/db/judge.db

CMD ["gunicorn", "-w", "3", "-b", "0.0.0.0:4399", "--access-logfile", "-", "web.run:app"]
