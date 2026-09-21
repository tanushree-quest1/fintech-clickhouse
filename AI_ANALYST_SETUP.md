# AI Analyst Integration Setup Guide

## Overview
This guide explains how to set up and use the AI Analyst feature that integrates LibreChat with ClickHouse MCP for natural language banking analytics queries.

## Architecture
```
Banking Dashboard (React)
    ↓ (AI Analyst Button)
LibreChat (http://localhost:3080)
    ↓ (MCP Protocol)
ClickHouse MCP Server (http://localhost:8001)
    ↓ (SQL Queries)
ClickHouse Database (bank_demo)
```

## Current Status
✅ **Completed:**
- ClickHouse MCP server configured and running (port 8001)
- LibreChat cloned and configured with MCP settings
- Docker compose override created for LibreChat + MongoDB
- AI Analyst floating button added to React dashboard
- Chat panel interface with LibreChat iframe integration
- Pre-built banking prompts included
- Groq endpoint configured for free LLM usage

⏳ **In Progress:**
- LibreChat Docker image being pulled and started

## Setup Instructions

### 1. Get a Free Groq API Key
1. Go to https://console.groq.com/
2. Create a free account (no credit card required)
3. Generate an API key
4. The free tier provides:
   - 30 requests/minute
   - 1,000 requests/day for most models
   - Up to 500K tokens/day for smaller models

### 2. Configure LibreChat API Key
Edit `LibreChat/.env` and set your Groq API key:
```bash
GROQ_API_KEY=your_actual_groq_api_key_here
```

### 3. Start LibreChat Services
```bash
docker compose -f docker-compose.yaml -f docker-compose.override.yml up -d librechat librechat-mongo
```

### 4. Verify Services
```bash
# Check ClickHouse MCP is running
curl http://localhost:8001/sse

# Check LibreChat is accessible
curl http://localhost:3080
```

### 5. Start Your Banking Dashboard
```bash
# Start backend
python -m backend.main

# Start frontend (in separate terminal)
cd frontend
npm run dev
```

### 6. Use the AI Analyst
1. Open your banking dashboard at http://localhost:5173
2. Click the blue floating button in the bottom-right corner
3. A chat panel will open with LibreChat embedded
4. Set your Groq API key in LibreChat if prompted
5. Enable the ClickHouse MCP server in the MCP settings
6. Ask banking questions like:
   - "Why did transaction failures increase?"
   - "Which merchants are most affected by the current issue?"
   - "Show me the gateway health status"
   - "What is the current success rate across all payment rails?"

## Quick Prompts
The AI Analyst panel includes these pre-built prompts:
- "Why did transaction failures increase?"
- "Which merchants are most affected?"
- "Show me the gateway health status"
- "What is the current success rate?"

## Troubleshooting

### LibreChat won't start
- Check if MongoDB is running: `docker ps | grep librechat-mongo`
- Check LibreChat logs: `docker logs bank-control-tower-librechat`
- Verify port 3080 is not in use

### MCP connection fails
- Verify ClickHouse MCP is running: `docker ps | grep mcp-clickhouse`
- Check MCP logs: `docker logs mcp-clickhouse`
- Ensure ClickHouse is accessible on localhost:8123

### Groq API errors
- Verify your API key is set in LibreChat/.env
- Check your Groq console for rate limits
- Try a different model if one is unavailable

### Frontend button not working
- Ensure LibreChat is accessible at http://localhost:3080
- Check browser console for iframe errors
- Verify CORS settings allow iframe embedding

## Configuration Files

### docker-compose.yaml
Added ClickHouse MCP server service:
```yaml
mcp-clickhouse:
  image: mcp/clickhouse
  container_name: mcp-clickhouse
  ports:
    - "8001:8000"
  environment:
    - CLICKHOUSE_HOST=host.docker.internal
    - CLICKHOUSE_PORT=8123
    - CLICKHOUSE_USER=demo
    - CLICKHOUSE_PASSWORD=demo_pass
    - CLICKHOUSE_DATABASE=bank_demo
    - CLICKHOUSE_MCP_SERVER_TRANSPORT=sse
```

### docker-compose.override.yml
Added LibreChat and MongoDB services with MCP configuration.

### LibreChat/librechat.yaml
Configured ClickHouse MCP server connection:
```yaml
mcpServers:
  clickhouse-local:
    type: sse
    url: http://host.docker.internal:8001/sse
```

### LibreChat/.env
Enabled Groq endpoint and configured for user-provided API key.

### Frontend Integration
- `AIAnalystPanel.tsx`: Chat panel component with LibreChat iframe
- `App.tsx`: Added AIAnalystButton component

## Next Steps
1. Get your Groq API key
2. Complete LibreChat startup
3. Test the AI Analyst with sample queries
4. Customize prompts for your specific use cases
5. Consider adding more MCP servers for additional data sources