FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the agent package only. `COPY . .` also dropped the repo root's legacy
# agent.py/__init__.py into /app, which made ADK read /app itself as one agent
# called "app" (serving the stale root agent) instead of discovering
# text2sql_agent inside it. Nothing else in the repo is needed at runtime:
# text2sql_agent imports only google-adk, google-cloud-bigquery and dotenv.
COPY text2sql_agent/ ./text2sql_agent/

# Set environment variables
ENV PORT=8000
ENV HOST=0.0.0.0

# Expose port
EXPOSE 8000

# Shell form so $PORT expands at runtime: hosts like Render assign the port and
# a container that ignores it never passes the health check.
#
# AGENTS_DIR is passed explicitly as /app, which now holds exactly one agent
# package. Left to its default it resolved to /, publishing an app called "app".
CMD exec python -m google.adk.cli api_server --port ${PORT:-8000} --host 0.0.0.0 /app
