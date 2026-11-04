// Konkursside lehe /konkursid/ staatused (Uus / Kaalun / Taotlen / Saadetud / Ei sobi)
// ja märge „Sandrale saadetud“. Aadress: /api/konkursid
//
// Cloudflare Pages Function. Vajab Cloudflare Pages'i seadetes:
//   • KV nimeruumi seost nimega KONKURSID   (Settings → Bindings → KV namespace)
//   • keskkonnamuutujat KONKURSID_TOKEN      (Settings → Variables and Secrets, „Encrypt“)
// Leht saadab võtme päises Authorization: Bearer <võti>. Võtme saab lehele
// üks kord lingiga /konkursid/?k=<võti> – leht jätab selle brauserisse meelde.
//
// GET  → { statuses: { <id>: { status, sentToSandra, at } } }
// POST { id, status?, sentToSandra? } → { ok: true }

const KEY = "statuses";
const STATUSES = new Set(["uus", "kaalun", "taotlen", "saadetud", "ei-sobi"]);

function authorized(request, env) {
  const want = (env.KONKURSID_TOKEN || "").trim();
  if (!want) return false;
  const got = (request.headers.get("authorization") || "").replace(/^Bearer\s+/i, "").trim();
  if (got.length !== want.length) return false;
  let diff = 0;
  for (let i = 0; i < want.length; i++) diff |= want.charCodeAt(i) ^ got.charCodeAt(i);
  return diff === 0;
}

const json = (obj, status = 200) =>
  Response.json(obj, { status, headers: { "cache-control": "no-store" } });

export async function onRequest(context) {
  const { request, env } = context;
  if (!env.KONKURSID) return json({ error: "KV seos puudub (KONKURSID)" }, 503);
  if (!authorized(request, env)) return json({ error: "vale või puuduv võti" }, 401);

  if (request.method === "GET") {
    const statuses = (await env.KONKURSID.get(KEY, "json")) || {};
    return json({ statuses });
  }

  if (request.method === "POST") {
    let body;
    try { body = await request.json(); } catch { return json({ error: "vigane JSON" }, 400); }
    const ids = Array.isArray(body.ids) ? body.ids : [body.id];
    if (!ids.length || ids.some((id) => typeof id !== "string" || !/^[a-z0-9-]{3,120}$/.test(id))) {
      return json({ error: "vale id" }, 400);
    }
    if (body.status !== undefined && !STATUSES.has(body.status)) return json({ error: "vale staatus" }, 400);
    const statuses = (await env.KONKURSID.get(KEY, "json")) || {};
    const now = new Date().toISOString();
    for (const id of ids) {
      const cur = statuses[id] || {};
      if (body.status !== undefined) cur.status = body.status;
      if (body.sentToSandra) cur.sentToSandra = now;
      cur.at = now;
      statuses[id] = cur;
    }
    await env.KONKURSID.put(KEY, JSON.stringify(statuses));
    return json({ ok: true });
  }

  return json({ error: "lubatud on GET ja POST" }, 405);
}
