/**
 * Single OAuth token rotation worker. Deploy with Verify JWT OFF, secured by
 * an independent high-entropy x-job-secret header from Supabase Vault.
 * Do NOT paste actual credentials into this source file.
 * IMPORTANT: Never retry an OAuth refresh request automatically.
 */
const DB_URL = Deno.env.get('DB_URL') || Deno.env.get('SUPABASE_URL') || '';
const DB_SERVICE_KEY = Deno.env.get('DB_SERVICE_KEY') || Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') || '';
const JOB_SECRET = Deno.env.get('CRON_JOB_SECRET') || '';
const CLIENT_ID = Deno.env.get('SALLA_CLIENT_ID') || '';
const CLIENT_SECRET = Deno.env.get('SALLA_CLIENT_SECRET') || '';

const pause = (ms: number) => new Promise((r) => setTimeout(r, ms));
const validConfig = Boolean(DB_URL.startsWith('https://') && !DB_URL.includes('/rest/v1') &&
  DB_SERVICE_KEY && !DB_SERVICE_KEY.startsWith('sb_publishable_') &&
  JOB_SECRET.length >= 32 && CLIENT_ID && CLIENT_SECRET);

async function rpc(name: string, body: Record<string, unknown>, attempts = 1): Promise<any> {
  let last: Error | null = null;
  for (let attempt = 0; attempt < attempts; attempt++) {
    try {
      const response = await fetch(`${DB_URL.replace(/\/$/, '')}/rest/v1/rpc/${name}`, {
        method: 'POST',
        headers: {
          'apikey': DB_SERVICE_KEY,
          ...(DB_SERVICE_KEY.startsWith('sb_secret_') ? {} : {'Authorization': `Bearer ${DB_SERVICE_KEY}`}),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(12000),
      });
      if (!response.ok) throw new Error(`DB RPC ${name}: HTTP ${response.status}`);
      return await response.json();
    } catch (e) {
      last = e instanceof Error ? e : new Error('DB RPC error');
      if (attempt + 1 < attempts) await pause(500 * (attempt + 1));
    }
  }
  throw last;
}

function ttlSeconds(data: Record<string, any>): number {
  // Salla's "expires" can be an epoch timestamp, whereas OAuth "expires_in" is a duration.
  const until = Number(data.expires_in ?? data.expires ?? 1209600);
  const ttl = until > 200000000 ? until - Math.floor(Date.now() / 1000) : until;
  return Number.isFinite(ttl) && ttl > 0 ? Math.min(Math.floor(ttl), 1209600) : 1209600;
}

async function rotateOne(row: {merchant_id: string; refresh_token: string; lock_nonce: string}) {
  const merchant = row.merchant_id;
  const mark = async (reason: string, reconnect = false) => {
    await rpc('salla_mark_refresh_error', {
      p_merchant_id: merchant, p_lock_nonce: row.lock_nonce,
      p_reason: reason, p_reconnect: reconnect,
    }, 3);
  };

  const body = new URLSearchParams({
    grant_type: 'refresh_token', client_id: CLIENT_ID,
    client_secret: CLIENT_SECRET, refresh_token: row.refresh_token,
  });
  let response: Response;
  try {
    // One-shot request. Never automatically repeat if the server may have consumed the token.
    response = await fetch('https://accounts.salla.sa/oauth2/token', {
      method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body, signal: AbortSignal.timeout(20000),
    });
  } catch (_e) {
    await mark('OAuth response unknown (network/timeout); do not retry old token');
    return {merchant_id: merchant, outcome: 'review_required'};
  }

  if (!response.ok) {
    let error = '';
    try { const data = await response.json(); error = String(data.error || ''); } catch (_) { /* no body */ }
    const invalid = response.status === 400 && error === 'invalid_grant';
    await mark(invalid ? 'invalid_grant; reauthorization required' : `OAuth HTTP ${response.status}; review manually`, invalid);
    return {merchant_id: merchant, outcome: invalid ? 'reconnect_required' : 'review_required'};
  }

  let data: Record<string, any>;
  try { data = await response.json(); }
  catch (_) {
    await mark('OAuth succeeded but unreadable response; do not retry old token');
    return {merchant_id: merchant, outcome: 'review_required'};
  }
  if (!data.access_token || !data.refresh_token) {
    await mark('OAuth response missing a token; do not retry old token');
    return {merchant_id: merchant, outcome: 'review_required'};
  }

  // Only database completion may be retried. NEVER redo the OAuth call.
  const ok = await rpc('salla_complete_rotation', {
    p_merchant_id: merchant, p_lock_nonce: row.lock_nonce,
    p_access_token: data.access_token, p_refresh_token: data.refresh_token,
    p_expires_in: ttlSeconds(data),
  }, 3);
  if (ok !== true) throw new Error(`Database refused token rotation for merchant ${merchant}`);
  return {merchant_id: merchant, outcome: 'connected'};
}

Deno.serve(async (req) => {
  if (req.method !== 'POST') return new Response('Method not allowed', {status: 405});
  if (!validConfig) return Response.json({error: 'Worker is not configured'}, {status: 503});
  if (req.headers.get('x-job-secret') !== JOB_SECRET) return Response.json({error: 'Unauthorized'}, {status: 401});
  try {
    await rpc('salla_quarantine_abandoned_refreshes', {}, 2);
    const rows = await rpc('salla_claim_due_tokens', {p_limit: 5}, 2);
    const results = [];
    // Serial rotation simplifies audits and avoids hitting OAuth rate limits.
    for (const row of rows as Array<{merchant_id: string; refresh_token: string; lock_nonce: string}>) {
      try { results.push(await rotateOne(row)); }
      catch (e) {
        console.error('Token rotation persistence failure for merchant', row.merchant_id, String(e instanceof Error ? e.message : 'error'));
        results.push({merchant_id: row.merchant_id, outcome: 'review_required'});
      }
    }
    return Response.json({checked: rows.length, results});
  } catch (e) {
    console.error('Token worker DB error', String(e instanceof Error ? e.message : 'error'));
    return Response.json({error: 'Worker failed'}, {status: 500});
  }
});
