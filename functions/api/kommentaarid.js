// Ühe video kommentaarid lehe /statistika/ jaoks. Aadress: /api/kommentaarid?v=VIDEO_ID
// Vajab Cloudflare Pages'i keskkonnamuutujat YT_API_KEY. Vastus jääb vahemällu 30 min.

const CACHE_SECONDS = 1800;

export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const id = url.searchParams.get("v") || "";
  if (!/^[A-Za-z0-9_-]{6,20}$/.test(id)) {
    return Response.json({ error: "vale video id" }, { status: 400 });
  }
  const key = (env.YT_API_KEY || "").trim();
  if (!key) return Response.json({ error: "API-võti puudub" }, { status: 503 });

  const cache = caches.default;
  const cacheKey = new Request(new URL(`/api/kommentaarid?v=${id}`, request.url).toString());
  const hit = await cache.match(cacheKey);
  if (hit) return hit;

  const api = `https://www.googleapis.com/youtube/v3/commentThreads?part=snippet,replies&videoId=${id}` +
    `&maxResults=50&order=relevance&textFormat=plainText&key=${key}`;
  const r = await fetch(api);
  const j = await r.json();

  if (!r.ok || j.error) {
    const reason = j.error && j.error.errors && j.error.errors[0] && j.error.errors[0].reason;
    if (reason === "commentsDisabled") {
      return Response.json({ comments: [], disabled: true }, { headers: { "cache-control": "public, max-age=3600" } });
    }
    return Response.json({ error: (j.error && j.error.message) || `HTTP ${r.status}` }, { status: 502 });
  }

  const pick = (s) => ({
    author: s.authorDisplayName || "",
    text: s.textDisplay || s.textOriginal || "",
    likes: s.likeCount || 0,
    published: s.publishedAt,
  });
  const comments = (j.items || []).map((t) => {
    const c = pick(t.snippet.topLevelComment.snippet);
    c.replies = ((t.replies && t.replies.comments) || [])
      .map((x) => pick(x.snippet))
      .sort((a, b) => new Date(a.published) - new Date(b.published));
    c.replyCount = t.snippet.totalReplyCount || 0;
    return c;
  });

  const res = Response.json({ comments }, { headers: { "cache-control": `public, max-age=${CACHE_SECONDS}` } });
  context.waitUntil(cache.put(cacheKey, res.clone()));
  return res;
}
