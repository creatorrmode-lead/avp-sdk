FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir agentveil mcp httpx

ENV AVP_BASE_URL=https://agentveil.dev
ENV AVP_AGENT_NAME=glama_inspector

CMD ["python", "-m", "mcp_server.server"]
