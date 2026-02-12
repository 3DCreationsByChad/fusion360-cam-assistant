@echo off
REM MCP-Link Bridge for Claude Desktop
REM This connects Claude Desktop directly to the MCP-Link server

REM Set the server URL and auth token
set SERVER_URL=https://127-0-0-1.local.aurafriday.com:31173/sse
set AUTH_TOKEN=Bearer 1816a663-12dd-4868-9658-e0bd65154d9e

REM Use npx mcp-remote with auth header
npx mcp-remote "%SERVER_URL%" -H "Authorization: %AUTH_TOKEN%"
