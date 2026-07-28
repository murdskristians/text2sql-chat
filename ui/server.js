const express = require('express');
const cors = require('cors');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;

// Agent API configuration. Defaults to a local agent: the old Cloud Run
// deployment lives in a project we no longer control, so falling back to it
// would silently answer from stale data.
//
// Render's fromService injects a bare hostname with no scheme, which fetch()
// rejects, so add one when it's missing.
const rawAgentUrl = process.env.AGENT_URL || 'http://localhost:8000';
const AGENT_URL = /^https?:\/\//.test(rawAgentUrl)
    ? rawAgentUrl.replace(/\/+$/, '')
    : `https://${rawAgentUrl.replace(/\/+$/, '')}`;

// Google Cloud configuration (for authenticated requests)
const GOOGLE_CLOUD_PROJECT = process.env.GOOGLE_CLOUD_PROJECT || 'smartsuitebigqueryproject';
const GOOGLE_CLOUD_LOCATION = process.env.GOOGLE_CLOUD_LOCATION || 'europe-west1';

// Per-IP rate limiting for the public demo. The agent is unauthenticated, so
// anything that costs Gemini quota or BigQuery scans needs a cap. Held in
// memory, which is fine on a single instance but would need Redis to scale out.
const RULES = [
    { prefix: '/api/chat', limit: 12, window: 300 },     // 12 questions / 5 min
    { prefix: '/api/session', limit: 30, window: 300 },
];
const GLOBAL_RULE = { limit: 120, window: 60 };

// Render terminates TLS at a proxy, so the real client IP is in
// X-Forwarded-For. Only trust it when we know we're behind a proxy - otherwise
// a caller could spoof the header to reset their own limit.
const TRUST_PROXY = ['1', 'true', 'yes'].includes(
    (process.env.TRUST_PROXY || '').toLowerCase()
);
if (TRUST_PROXY) app.set('trust proxy', 1);

const hits = new Map();

function overLimit(key, limit, window, now) {
    const cutoff = now - window * 1000;
    const recent = (hits.get(key) || []).filter((t) => t >= cutoff);
    if (recent.length >= limit) {
        hits.set(key, recent);
        return true;
    }
    recent.push(now);
    hits.set(key, recent);
    return false;
}

function rateLimit(req, res, next) {
    // Preflight costs nothing and must not consume budget, or a browser's
    // OPTIONS could exhaust the limit before the real request is sent.
    if (req.method === 'OPTIONS') return next();

    const ip = TRUST_PROXY ? req.ip : req.socket.remoteAddress || 'unknown';
    const now = Date.now();

    if (overLimit(`${ip}:*`, GLOBAL_RULE.limit, GLOBAL_RULE.window, now)) {
        return tooMany(res, GLOBAL_RULE.window);
    }

    // Mounted at /api, so req.path has that prefix stripped - rejoin it or the
    // per-route rules below never match.
    const fullPath = (req.baseUrl || '') + req.path;
    const rule = RULES.find((r) => fullPath.startsWith(r.prefix));
    if (rule && overLimit(`${ip}:${rule.prefix}`, rule.limit, rule.window, now)) {
        return tooMany(res, rule.window);
    }

    next();
}

function tooMany(res, window) {
    return res.status(429).set('Retry-After', String(window)).json({
        error:
            'Rate limit reached for this demo. Please wait up to ' +
            `${Math.floor(window / 60) || 1} minute(s) and try again.`,
    });
}

// Drop IPs that have gone quiet, so the map can't grow without bound.
setInterval(() => {
    const cutoff = Date.now() - 300 * 1000;
    for (const [key, times] of hits) {
        if (!times.some((t) => t >= cutoff)) hits.delete(key);
    }
}, 60 * 1000).unref();

// Middleware
app.use(cors());
app.use(express.json());
app.use('/api', rateLimit);
app.use(express.static(path.join(__dirname, 'public')));

// Helper function to get authentication headers if needed
async function getAuthHeaders() {
    const headers = {
        'Content-Type': 'application/json',
    };

    // If running in authenticated mode, try to get identity token
    if (process.env.GOOGLE_APPLICATION_CREDENTIALS || process.env.GOOGLE_GENAI_USE_VERTEXAI) {
        try {
            const { GoogleAuth } = require('google-auth-library');
            const auth = new GoogleAuth();
            const client = await auth.getIdTokenClient(AGENT_URL);
            const token = await client.idTokenProvider.fetchIdToken(AGENT_URL);
            headers['Authorization'] = `Bearer ${token}`;
        } catch (error) {
            console.log('Running without authentication (agent allows unauthenticated access)');
        }
    }

    return headers;
}

// Proxy endpoint for agent API
app.post('/api/chat', async (req, res) => {
    const { message, sessionId, userId, appName } = req.body;

    try {
        const headers = await getAuthHeaders();

        const agentResponse = await fetch(`${AGENT_URL}/run_sse`, {
            method: 'POST',
            headers,
            body: JSON.stringify({
                app_name: appName || 'text2sql_agent',
                user_id: userId || 'local-user',
                session_id: sessionId,
                new_message: {
                    role: 'user',
                    parts: [{ text: message }]
                },
                streaming: true
            })
        });

        if (!agentResponse.ok) {
            const errorText = await agentResponse.text();
            console.error('Agent error:', agentResponse.status, errorText);
            return res.status(agentResponse.status).json({
                error: `Agent returned ${agentResponse.status}: ${errorText}`
            });
        }

        // Set headers for SSE
        res.setHeader('Content-Type', 'text/event-stream');
        res.setHeader('Cache-Control', 'no-cache');
        res.setHeader('Connection', 'keep-alive');
        res.setHeader('X-Accel-Buffering', 'no');

        // Stream the response
        const reader = agentResponse.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            const chunk = decoder.decode(value, { stream: true });
            res.write(chunk);
        }

        res.end();
    } catch (error) {
        console.error('Error proxying to agent:', error);
        res.status(500).json({ error: error.message });
    }
});

// Create session endpoint
app.post('/api/session', async (req, res) => {
    const { userId, appName } = req.body;

    try {
        const headers = await getAuthHeaders();
        const sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

        const response = await fetch(
            `${AGENT_URL}/apps/${appName || 'text2sql_agent'}/users/${userId}/sessions/${sessionId}`,
            {
                method: 'POST',
                headers,
                body: JSON.stringify({ state: {} })
            }
        );

        if (response.ok) {
            const data = await response.json();
            res.json({ id: sessionId, ...data });
        } else {
            // If session creation fails, just return a local session ID
            res.json({ id: sessionId });
        }
    } catch (error) {
        console.error('Error creating session:', error);
        // Return a local session ID even on error
        const sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        res.json({ id: sessionId });
    }
});

// List apps endpoint
app.get('/api/apps', async (req, res) => {
    try {
        const headers = await getAuthHeaders();
        const response = await fetch(`${AGENT_URL}/list-apps`, { headers });
        const data = await response.json();
        res.json(data);
    } catch (error) {
        console.error('Error listing apps:', error);
        res.status(500).json({ error: error.message });
    }
});

// Health check endpoint
app.get('/api/health', async (req, res) => {
    try {
        const response = await fetch(`${AGENT_URL}/list-apps`);
        if (response.ok) {
            res.json({ status: 'healthy', agentUrl: AGENT_URL });
        } else {
            res.status(503).json({ status: 'unhealthy', error: 'Agent not responding' });
        }
    } catch (error) {
        res.status(503).json({ status: 'unhealthy', error: error.message });
    }
});

// Serve the main page
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => {
    console.log(`\n🚀 Reltek Data Assistant UI running at http://localhost:${PORT}`);
    console.log(`📡 Agent URL: ${AGENT_URL}`);
    console.log(`☁️  Project: ${GOOGLE_CLOUD_PROJECT}`);
    console.log(`📍 Location: ${GOOGLE_CLOUD_LOCATION}\n`);
});
