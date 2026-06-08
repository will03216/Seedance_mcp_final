FROM python:3.11-slim
WORKDIR /app

COPY packages/seedance-sdk ./packages/seedance-sdk
COPY packages/seedance-mcp ./packages/seedance-mcp

RUN pip install --no-cache-dir \
    ./packages/seedance-sdk \
    ./packages/seedance-mcp

ENV MCP_TRANSPORT=sse
EXPOSE 8000
CMD ["python", "-m", "seedance_mcp"]
