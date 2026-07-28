FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PORT=8000
ENV HOST=0.0.0.0

# Expose port
EXPOSE 8000

# Shell form so $PORT expands at runtime: hosts like Render assign the port and
# a container that ignores it never passes the health check.
#
# AGENTS_DIR is passed explicitly as /app. Left to its default it resolved to /,
# where the *app directory itself* looks like a single agent (the repo root has
# __init__.py and agent.py), so the server published one app called "app"
# running the stale root-level agent instead of text2sql_agent.
CMD exec python -m google.adk.cli api_server --port ${PORT:-8000} --host 0.0.0.0 /app
