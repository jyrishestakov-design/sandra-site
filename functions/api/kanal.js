// Kanali "Mida teie ka kunstist taipate?" (VÄLJASÕIT / fieldnotes) statistika
// lehe /statistika/ jaoks. Aadress: /api/kanal
//
// Cloudflare Pages Function (kaust functions/ → aadress /api/kanal).
// Ilma võtmeta: YouTube'i RSS-voog (15 viimast videot).
// Cloudflare Pages'i keskkonnamuutujaga YT_API_KEY (Settings → Variables and Secrets):
// kõik videod, tellijad, koguvaatamised, kommentaarid.
// Vastust hoitakse Cloudflare'i vahemälus 30 min, nii et YouTube'i poole pöördutakse harva.

const CHANNEL_ID = "UC_sWsL0FT6ppF0Te1BMh0dQ";

const decode = (s) =>
  s.replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
   .replace(/&quot;/g, '"').replace(/&#39;/g, "'")
   .replace(/&#(\d+);/g, (_, d) => String.fromCharCode(+d));

async function rss() {
  const r = await fetch(`https://www.youtube.com/feeds/videos.xml?channel_id=${CHANNEL_ID}`);
  if (!r.ok) throw new Error(`RSS HTTP ${r.status}`);
  const xml = await r.text();
  const channelTitle = decode((xml.match(/<title>([^<]*)<\/title>/) || [])[1] || "");
  const videos = xml.split("<entry>").slice(1).map((e) => ({
    id: (e.match(/<yt:videoId>([^<]+)</) || [])[1],
    title: decode((e.match(/<title>([^<]*)<\/title>/) || [])[1] || ""),
    published: (e.match(/<published>([^<]+)</) || [])[1],
    views: +((e.match(/media:statistics views="(\d+)"/) || [])[1] || 0),
    likes: (() => { const m = e.match(/media:starRating count="(\d+)"/); return m ? +m[1] : null; })(),
    comments: null,
  })).filter((v) => v.id);
  if (!videos.length) throw new Error("RSS-voog tühi");
  return { channelTitle, stats: {}, videos, source: "RSS" };
}

async function getJSON(url) {
  const r = await fetch(url);
  const j = await r.json();
  if (!r.ok || j.error) throw new Error((j.error && j.error.message) || `API HTTP ${r.status}`);
  return j;
}

async function api(key) {
  const base = "https://www.googleapis.com/youtube/v3";
  const ch = await getJSON(`${base}/channels?part=snippet,statistics,contentDetails&id=${CHANNEL_ID}&key=${key}`);
  const item = (ch.items || [])[0];
  if (!item) throw new Error("kanalit ei leitud");
  const uploads = item.contentDetails.relatedPlaylists.uploads;
  let ids = [], token = null;
  do {
    const pl = await getJSON(`${base}/playlistItems?part=contentDetails&maxResults=50&playlistId=${uploads}&key=${key}` + (token ? `&pageToken=${token}` : ""));
    ids = ids.concat((pl.items || []).map((i) => i.contentDetails.videoId));
    token = pl.nextPageToken || null;
  } while (token && ids.length < 5000);
  let videos = [];
  for (let i = 0; i < ids.length; i += 50) {
    const vj = await getJSON(`${base}/videos?part=snippet,statistics&id=${ids.slice(i, i + 50).join(",")}&key=${key}`);
    videos = videos.concat((vj.items || []).map((v) => ({
      id: v.id,
      title: v.snippet.title,
      published: v.snippet.publishedAt,
      views: +(v.statistics.viewCount || 0),
      likes: v.statistics.likeCount != null ? +v.statistics.likeCount : null,
      comments: v.statistics.commentCount != null ? +v.statistics.commentCount : null,
    })));
  }
  const st = item.statistics;
  return {
    channelTitle: item.snippet.title,
    stats: { subs: st.hiddenSubscriberCount ? null : +st.subscriberCount, totalViews: +st.viewCount },
    videos,
    source: "API",
  };
}

const CACHE_SECONDS = 1800;

export async function onRequest(context) {
  const { request, env } = context;
  const fresh = new URL(request.url).searchParams.has("fresh");
  const cacheKey = new Request(new URL("/api/kanal", request.url).toString());
  const cache = caches.default;

  if (!fresh) {
    const hit = await cache.match(cacheKey);
    if (hit) return hit;
  }

  // Viimane õnnestunud seis (hoitakse 7 päeva), kui YouTube parasjagu ei vasta.
  const lastGoodKey = new Request(new URL("/api/kanal-viimane", request.url).toString());

  const res = await build((env.YT_API_KEY || "").trim());
  if (res.ok) {
    const body = await res.clone().text();
    context.waitUntil(Promise.all([
      cache.put(cacheKey, res.clone()),
      cache.put(lastGoodKey, new Response(body, {
        headers: { "content-type": "application/json", "cache-control": "public, max-age=604800" },
      })),
    ]));
    return res;
  }
  const last = await cache.match(lastGoodKey);
  if (last) {
    const data = await last.json();
    data.stale = true;
    data.error = (await res.json()).error;
    return Response.json(data, { headers: { "cache-control": "no-store" } });
  }
  return res;
}

async function build(key) {
  let data, error = null;
  try {
    if (key) {
      try { data = await api(key); }
      catch (e) { error = "API: " + e.message; data = await rss(); }
    } else {
      data = await rss();
    }
  } catch (e) {
    return Response.json({ error: e.message }, { status: 502, headers: { "cache-control": "no-store" } });
  }
  data.fetched = Date.now();
  if (error) data.error = error;
  return Response.json(data, {
    headers: { "cache-control": `public, max-age=${CACHE_SECONDS}` },
  });
}
