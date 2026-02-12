#!/usr/bin/env node
/**
 * MCP-Link Bridge for Claude Desktop
 *
 * This script acts as a stdio MCP server that forwards requests to MCP-Link
 * with proper Bearer token authentication.
 *
 * Claude Desktop → This Script (stdio) → MCP-Link Server (SSE + auth)
 */

const https = require('https');
const http = require('http');
const { URL } = require('url');

// Configuration
const SERVER_URL = 'https://127-0-0-1.local.aurafriday.com:31173';
const AUTH_TOKEN = 'Bearer 1816a663-12dd-4868-9658-e0bd65154d9e';

// Disable SSL certificate validation (for local development)
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';

// Parse server URL
const serverUrl = new URL(SERVER_URL);
const isHttps = serverUrl.protocol === 'https:';

// Message ID counter
let messageId = 0;

// Active SSE connection
let sseConnection = null;
let pendingRequests = new Map();

/**
 * Log to stderr (stdout is reserved for JSON-RPC)
 */
function log(message) {
  console.error(`[MCP-Bridge] ${message}`);
}

/**
 * Send JSON-RPC response to Claude Desktop
 */
function sendResponse(response) {
  console.log(JSON.stringify(response));
}

/**
 * Connect to MCP-Link SSE endpoint
 */
async function connectSSE() {
  return new Promise((resolve, reject) => {
    log('Connecting to MCP-Link server...');

    const options = {
      hostname: serverUrl.hostname,
      port: serverUrl.port,
      path: '/sse',
      method: 'GET',
      headers: {
        'Accept': 'text/event-stream',
        'Authorization': AUTH_TOKEN,
        'Cache-Control': 'no-cache'
      }
    };

    const client = isHttps ? https : http;
    const req = client.request(options, (res) => {
      if (res.statusCode !== 200) {
        reject(new Error(`HTTP ${res.statusCode}`));
        return;
      }

      log(`Connected! Status: ${res.statusCode}`);

      let buffer = '';
      let sessionId = null;
      let messageEndpoint = null;

      res.on('data', (chunk) => {
        buffer += chunk.toString();
        const lines = buffer.split('\n');
        buffer = lines.pop(); // Keep incomplete line in buffer

        let eventType = null;
        for (const line of lines) {
          if (line.startsWith('event:')) {
            eventType = line.substring(6).trim();
          } else if (line.startsWith('data:')) {
            const data = line.substring(5).trim();

            if (eventType === 'endpoint') {
              messageEndpoint = data;
              if (data.includes('session_id=')) {
                sessionId = data.split('session_id=')[1].split('&')[0];
              }
              log(`Session ID: ${sessionId}`);
              log(`Message endpoint: ${messageEndpoint}`);
            } else {
              // Handle JSON messages
              try {
                const json = JSON.parse(data);

                // Handle reverse calls
                if (json.reverse) {
                  log(`Reverse call received: ${JSON.stringify(json.reverse)}`);
                  // For now, just log - fusion360 handles these
                }

                // Handle responses to our requests
                if (json.id && pendingRequests.has(json.id)) {
                  const resolver = pendingRequests.get(json.id);
                  pendingRequests.delete(json.id);
                  resolver(json);
                }
              } catch (e) {
                // Not JSON, ignore
              }
            }
          }
        }
      });

      res.on('end', () => {
        log('SSE connection closed');
        sseConnection = null;
      });

      // Store connection info
      sseConnection = {
        sessionId,
        messageEndpoint,
        req
      };

      resolve(sseConnection);
    });

    req.on('error', (err) => {
      log(`Connection error: ${err.message}`);
      reject(err);
    });

    req.end();
  });
}

/**
 * Send request to MCP-Link server
 */
async function sendToServer(method, params) {
  if (!sseConnection) {
    throw new Error('Not connected to server');
  }

  const requestId = `req-${++messageId}`;

  const request = {
    jsonrpc: '2.0',
    id: requestId,
    method: method,
    params: params
  };

  const body = JSON.stringify(request);

  return new Promise((resolve, reject) => {
    const options = {
      hostname: serverUrl.hostname,
      port: serverUrl.port,
      path: sseConnection.messageEndpoint,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(body),
        'Authorization': AUTH_TOKEN
      }
    };

    const client = isHttps ? https : http;
    const req = client.request(options, (res) => {
      if (res.statusCode !== 202) {
        reject(new Error(`HTTP ${res.statusCode}`));
        return;
      }

      // Store resolver for when response comes via SSE
      pendingRequests.set(requestId, resolve);

      // Timeout after 30 seconds
      setTimeout(() => {
        if (pendingRequests.has(requestId)) {
          pendingRequests.delete(requestId);
          reject(new Error('Request timeout'));
        }
      }, 30000);
    });

    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

/**
 * Handle JSON-RPC request from Claude Desktop
 */
async function handleRequest(request) {
  const { method, params, id } = request;

  log(`Request: ${method}`);

  try {
    // Initialize connection on first request
    if (!sseConnection && method === 'initialize') {
      await connectSSE();
    }

    // Forward request to MCP-Link server
    const response = await sendToServer(method, params);

    // Send response back to Claude Desktop
    sendResponse({
      jsonrpc: '2.0',
      id: id,
      result: response.result || response
    });

  } catch (error) {
    log(`Error: ${error.message}`);
    sendResponse({
      jsonrpc: '2.0',
      id: id,
      error: {
        code: -32603,
        message: error.message
      }
    });
  }
}

/**
 * Main: Read JSON-RPC from stdin
 */
async function main() {
  log('MCP-Link Bridge starting...');
  log(`Server: ${SERVER_URL}`);

  let buffer = '';

  process.stdin.on('data', (chunk) => {
    buffer += chunk.toString();

    // Process complete JSON objects
    let newlineIndex;
    while ((newlineIndex = buffer.indexOf('\n')) !== -1) {
      const line = buffer.substring(0, newlineIndex).trim();
      buffer = buffer.substring(newlineIndex + 1);

      if (line) {
        try {
          const request = JSON.parse(line);
          handleRequest(request).catch(err => {
            log(`Handler error: ${err.message}`);
          });
        } catch (e) {
          log(`JSON parse error: ${e.message}`);
        }
      }
    }
  });

  process.stdin.on('end', () => {
    log('stdin closed, exiting');
    process.exit(0);
  });

  // Keep process alive
  process.stdin.resume();
}

// Handle errors
process.on('uncaughtException', (err) => {
  log(`Uncaught exception: ${err.message}`);
  process.exit(1);
});

process.on('unhandledRejection', (err) => {
  log(`Unhandled rejection: ${err.message}`);
  process.exit(1);
});

main().catch(err => {
  log(`Fatal error: ${err.message}`);
  process.exit(1);
});
