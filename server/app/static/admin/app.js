// The parents' page of colors (the project folder and container are still called kidtube). Plain JavaScript modules, no build step (ADR 0025). Looks: the kidtube design system.
// Text from YouTube or Plex is always set with textContent, never as HTML.

const app = document.getElementById("app");
const nav = document.getElementById("nav");
let profiles = [];
let timer = null;

// ---- helpers ------------------------------------------------------------------------------------------------------

function h(tag, props = {}, ...kids) {
  const el = document.createElementNS(tag === "svg" || tag === "path" || tag === "circle" ? "http://www.w3.org/2000/svg" : "http://www.w3.org/1999/xhtml", tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v == null || v === false) continue;
    if (k === "class") el.setAttribute("class", v);
    else if (k === "style") el.setAttribute("style", v);
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (v === true) el.setAttribute(k, "");
    else el.setAttribute(k, v);
  }
  for (const kid of kids.flat(Infinity)) if (kid != null && kid !== false) el.append(kid);
  return el;
}

// replaceChildren, but flattening arrays and dropping null/false (so they never show as text).
function fill(el, ...kids) {
  el.replaceChildren(...kids.flat(Infinity).filter((k) => k != null && k !== false && k !== ""));
  return el;
}

const ICONS = {
  back: "M15 5l-7 7 7 7",
  check: "M5 12.5l4.5 4.5L19 7.5",
  plus: "M12 5v14M5 12h14",
  x: "M6 6l12 12M18 6L6 18",
  retry: "M4 12a8 8 0 1 0 2.4-5.7M4 4v4h4",
  play: "M8 5.5v13l10-6.5z",
};
const icon = (name) => h("svg", { viewBox: "0 0 24 24", "aria-hidden": "true" }, h("path", { d: ICONS[name] }));
const iconBtn = (name, label, onclick, primary) =>
  h("button", { class: "kt-iconbtn" + (primary ? " kt-iconbtn--primary" : ""), type: "button", "aria-label": label, title: label, onclick }, icon(name));

function toast(text) {
  document.querySelector(".toast")?.remove();
  const t = h("div", { class: "toast", role: "status" }, text);
  document.body.append(t);
  setTimeout(() => t.remove(), 3500);
}

async function api(path, { method = "GET", body } = {}) {
  const res = await fetch("/api/admin" + path, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401 && !path.startsWith("/auth")) {
    signIn();
    throw new Error("Please sign in.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail;
    throw new Error(typeof d === "string" ? d : (d && d.message) || (Array.isArray(d) ? "Check the values you entered." : "Something went wrong."));
  }
  return data;
}

async function run(fn) {
  try { return await fn(); } catch (e) { toast(e.message); }
}

const mins = (s) => {
  if (!s) return "";
  s = Math.round(s);
  const hh = Math.floor(s / 3600), mm = Math.floor((s % 3600) / 60), ss = s % 60;
  return hh ? `${hh}:${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}` : `${mm}:${String(ss).padStart(2, "0")}`;
};
const minutesText = (s) => {
  const m = Math.round((s || 0) / 60);
  return m >= 60 ? `${Math.floor(m / 60)} h ${m % 60} min` : `${m} min`;
};
const ago = (t) => {
  if (!t) return "";
  const d = (Date.now() / 1000 - t) / 86400;
  if (d < 1) return "today";
  if (d < 2) return "yesterday";
  if (d < 30) return `${Math.floor(d)} days ago`;
  return new Date(t * 1000).toLocaleDateString();
};
const go = (hash) => { location.hash = hash; };

// The name, one colour per letter (ADR 0038). The colours come from app.css.
const wordmark = () => h("span", { class: "kt-wordmark", role: "img", "aria-label": "colors" }, [..."colors"].map((c) => h("span", { "aria-hidden": "true" }, c)));

// ---- theme (ADR 0033): System, Light or Dark, kept per device ----------------------------------------------------
function getTheme() { try { return localStorage.getItem("kt-theme") || "system"; } catch { return "system"; } }
function setTheme(t) {
  try { t === "system" ? localStorage.removeItem("kt-theme") : localStorage.setItem("kt-theme", t); } catch {}
  if (t === "light" || t === "dark") document.documentElement.setAttribute("data-theme", t);
  else document.documentElement.removeAttribute("data-theme");
}
const isDark = () => document.documentElement.getAttribute("data-theme") === "dark" ||
  (!document.documentElement.hasAttribute("data-theme") && matchMedia("(prefers-color-scheme: dark)").matches);

// ---- loading (ADR 0031): placeholders in the shape of what is coming, one line saying what is happening ---------
const skel = (cls, style) => h("div", { class: "kt-skel " + cls, style, "aria-hidden": "true" });
function skelRows(n = 4) {
  return Array.from({ length: n }, () => h("div", { class: "skel-row" }, skel("kt-skel--thumb"),
    h("div", {}, skel("kt-skel--title"), skel("kt-skel--line", "width:50%"))));
}
function skelChannel() {
  return h("div", { class: "kt-stack center", style: "gap:10px" }, skel("kt-skel--round", "width:96px;height:96px"),
    skel("kt-skel--title", "width:50%"), skel("kt-skel--line", "width:35%"));
}
function skelGrid(n = 4) {
  return h("div", { class: "kt-grid" }, Array.from({ length: n }, () => h("div", { class: "kt-stack", style: "gap:8px" },
    skel("kt-skel--big"), skel("kt-skel--title"))));
}
const loadingLine = (text) => h("div", { class: "loading-line", role: "status" }, h("span", { class: "kt-spinner" }), text);
function busy(btn, on = true) { if (btn) on ? btn.setAttribute("aria-busy", "true") : btn.removeAttribute("aria-busy"); }

// ---- pictures: channels (ADR 0030) and profiles (ADR 0036) -----------------------------------------------------
const isChannelId = (x) => /^[A-Za-z0-9_-]{3,64}$/.test(x || "");
function chanAvatar(channelId, fallbackUrl, title, cls = "") {
  const el = h("span", { class: `kt-avatar kt-avatar--plain ${cls}`, "aria-hidden": "true" });
  const tries = [isChannelId(channelId) ? `/api/admin/channel-pictures/${encodeURIComponent(channelId)}` : null, fallbackUrl].filter(Boolean);
  const next = () => {
    const src = tries.shift();
    if (!src) return fill(el, (title || "?").slice(0, 1).toUpperCase());
    const img = h("img", { src, alt: "", loading: "lazy" });
    img.onerror = next;
    fill(el, img);
  };
  next();
  return el;
}
// A letter now; the picture once the server has found it (search answers before pictures are looked up).
function laterAvatar(channelId, title, cls = "") {
  const el = avatar("", title, `kt-avatar--plain ${cls}`);
  if (isChannelId(channelId)) el.dataset.cid = channelId;
  return el;
}
function watchPictures(root) {
  let left = [...new Set([...root.querySelectorAll("[data-cid]")].map((e) => e.dataset.cid))];
  if (!left.length) return;
  [1500, 4000, 8000, 15000].forEach((ms) => setTimeout(async () => {
    if (!left.length || !root.isConnected) return;
    const r = await api("/channel-pictures?ids=" + left.join(",")).catch(() => ({ ready: [] }));
    for (const id of r.ready) {
      for (const el of root.querySelectorAll(`[data-cid="${id}"]`)) {
        const img = h("img", { src: `/api/admin/channel-pictures/${id}`, alt: "" });
        img.onload = () => fill(el, img);
        delete el.dataset.cid;
      }
    }
    left = left.filter((x) => !r.ready.includes(x));
  }, ms));
}
function profileAvatar(p, cls = "") {
  const color = p.avatar_color ? ` av--${p.avatar_color}` : "";
  if (p.avatar_url) return h("span", { class: `kt-avatar av${color} ${cls}`, "aria-hidden": "true" }, h("img", { src: p.avatar_url, alt: "" }));
  return h("span", { class: `kt-avatar${color} ${cls}`, "aria-hidden": "true" }, (p.name || "?").slice(0, 1).toUpperCase());
}

function itemThumb(it) {
  return it.has_thumb ? `/api/admin/items/${it.id}/thumb` : (it.thumb_url || "");
}

function thumb(src, opts = {}) {
  return h("div", { class: "kt-thumb", style: opts.style, onclick: opts.onclick },
    src ? h("img", { src, alt: "", loading: "lazy" }) : null,
    opts.time ? h("span", { class: "kt-thumb__time" }, mins(opts.time)) : null,
    opts.seen ? h("span", { class: "kt-thumb__seen" }, h("i", { style: `width:${Math.round(opts.seen * 100)}%` })) : null);
}

function avatar(src, letter, cls = "") {
  return h("span", { class: `kt-avatar ${cls}`, "aria-hidden": "true" }, src ? h("img", { src, alt: "", loading: "lazy" }) : (letter || "?").slice(0, 1).toUpperCase());
}


// `search` puts a search box in the bar, in one row with the action (the Library: search, then Add).
function topBar(title, { back, action, search } = {}) {
  return h("div", { class: search ? "kt-top kt-top--search" : "kt-top" },
    back ? h("button", { class: "kt-iconbtn", type: "button", "aria-label": "Back", onclick: () => (history.length > 1 ? history.back() : go(back)) }, icon("back")) : null,
    h("h1", { class: "kt-top__title" }, title),
    search || null,
    action || null);
}

let screensDrawn = 0;  // the router's "slow screen" placeholder only shows while nothing has been drawn yet
function screen(title, opts, ...body) {
  screensDrawn++;
  fill(app, topBar(title, opts), h("div", { class: "content" }, ...body));
  window.scrollTo(0, 0);
}

function switchBtn(on, label, onchange) {
  const b = h("button", { class: "kt-switch", type: "button", "aria-pressed": on ? "true" : "false", "aria-label": label });
  b.addEventListener("click", () => {
    const next = b.getAttribute("aria-pressed") !== "true";
    b.setAttribute("aria-pressed", String(next));
    onchange(next);
  });
  return b;
}

function row(label, right, sub) {
  return h("div", { class: "kt-list__row" }, h("span", { class: "kt-list__text" }, label, sub ? h("span", { class: "kt-muted" }, sub) : null), right ?? null);
}
const linkRow = (label, value, hash) =>
  h("a", { class: "kt-list__row", href: "#" + hash }, h("span", { class: "kt-list__text" }, label), value != null ? h("span", { class: "kt-list__value" }, value) : null);

function profileChips(selected, onchange) {
  const set = new Set(selected);
  return h("div", { class: "kt-row" }, profiles.map((p) =>
    h("button", { class: "kt-chip", type: "button", "aria-pressed": set.has(p.id) ? "true" : "false", onclick: (e) => {
      set.has(p.id) ? set.delete(p.id) : set.add(p.id);
      e.currentTarget.setAttribute("aria-pressed", String(set.has(p.id)));
      onchange([...set], p.id, set.has(p.id));
    } }, p.name)));
}

function preview(externalId) {
  return h("iframe", { class: "preview", allowfullscreen: true, title: "Preview", src: `https://www.youtube-nocookie.com/embed/${encodeURIComponent(externalId)}?autoplay=1` });
}

// ---- sign in ------------------------------------------------------------------------------------------------------

async function signIn() {
  nav.hidden = true;
  clearInterval(timer);
  activityEl.hidden = true;
  const st = await api("/auth");
  if (st.authed) return start();
  const first = !st.password_set;
  const pw = h("input", { id: "pw", class: "kt-input", type: "password", autocomplete: first ? "new-password" : "current-password", required: true, minlength: 6 });
  fill(app, h("div", { class: "content", style: "padding-top:48px; gap:24px" },
    h("h1", { class: "h-display" }, wordmark()),
    h("p", { style: "margin:0" }, first ? "Only what you approved, for as long as you allow. First, set a password for this page." : "Sign in to the parents' page."),
    h("form", { class: "kt-stack", onsubmit: (e) => { e.preventDefault(); run(async () => {
      await api(first ? "/auth/setup" : "/auth/login", { method: "POST", body: { password: pw.value } });
      start();
    }); } },
      h("div", { class: "kt-field" }, h("label", { for: "pw" }, "Parents' password"), pw),
      h("button", { class: "kt-btn kt-btn--primary kt-btn--wide" }, first ? "Set password" : "Sign in"))));
  pw.focus();
}

// ---- Library: what the boys can watch, the one search box, and Add (ADR 0037) -------------------------------------

const isWide = () => matchMedia("(min-width: 900px)").matches;
const namesOf = (ids) => profiles.filter((p) => ids.includes(p.id)).map((p) => p.name).join(" and ") || "nobody";

// Who newly added videos are for. Remembered on this device; both boys until a parent changes it.
function forIds() {
  const kids = profiles.filter((p) => p.kind === "child").map((p) => p.id);
  try {
    const saved = JSON.parse(localStorage.getItem("kt-add-for") || "null");
    if (Array.isArray(saved)) return saved.filter((id) => profiles.some((p) => p.id === id));
  } catch {}
  return kids;
}
function forRow() {
  return h("div", { class: "kt-row for-row" }, h("span", { class: "kt-muted" }, "Add for"),
    profileChips(forIds(), (ids) => { try { localStorage.setItem("kt-add-for", JSON.stringify(ids)); } catch {} }));
}

function videoRow(v, { onOpen, right } = {}) {
  const prev = h("div");
  const open = onOpen || (() => fill(prev, preview(v.external_id)));
  const body = h("div", { class: "kt-video__body" },
    h("div", { class: "kt-video__title clickable", onclick: open }, v.title),
    h("div", { class: "kt-muted" }, [v.channel_title || v.container_title, v.upload_date].filter(Boolean).join(" · ")),
    right ? h("div", { class: "kt-row", style: "margin-top:4px" }, right) : null);
  const r = h("div", { class: "kt-video" }, thumb(v.thumb_url || itemThumb(v), { time: v.duration_s, onclick: open }), body);
  return h("div", { class: "kt-stack", style: "gap:8px" }, r, prev);
}

function addButtons(v) {
  if (v.in_library) return h("span", { class: "kt-tag kt-tag--ok" }, "In your library");
  const holder = h("span");
  holder.append(h("button", { class: "kt-btn kt-btn--primary kt-btn--sm", type: "button", onclick: (e) => run(async () => {
    const ids = forIds();
    if (!ids.length) throw new Error("Choose who it's for first, at the top.");
    busy(e.currentTarget);
    const r = await api("/add", { method: "POST", body: { urls: [v.url], approve: true, profile_ids: ids } });
    if (r.failed.length) { busy(e.target, false); throw new Error(r.failed[0].error); }
    fill(holder, h("span", { class: "kt-tag kt-tag--ok" }, `Added for ${namesOf(ids)}`));
    v.in_library = true;
    toast(`Added for ${namesOf(ids)}. It's downloading now.`);
    kickActivity();
  }) }, icon("plus"), "Add"));
  return holder;
}

function searchForm(value = "") {
  const q = h("input", { id: "q", class: "kt-input kt-input--search", type: "search", value, enterkeyhint: "search",
    placeholder: "Search library, YouTube, Plex" });
  return h("form", { class: "search-form", onsubmit: (e) => { e.preventDefault(); const t = q.value.trim(); if (t) go("find/" + encodeURIComponent(t)); } },
    h("label", { for: "q", class: "sr" }, "Search your library, YouTube and Plex, or paste a YouTube link"), q);
}

const libState = { who: 0, view: "channels", page: 1 };
const PAGE = 24;

/** Numbered pages: Previous, 1 … 4 5 6 … 12, Next. Nothing when it all fits on one page. */
function pager(page, pages, onGo) {
  if (pages <= 1) return null;
  const nums = [...new Set([1, page - 1, page, page + 1, pages])].filter((n) => n >= 1 && n <= pages).sort((a, b) => a - b);
  const out = [];
  nums.forEach((n, i) => {
    if (i && n - nums[i - 1] > 1) out.push(h("span", { class: "kt-muted pager__gap" }, "…"));
    out.push(h("button", { class: "kt-chip", type: "button", "aria-pressed": n === page ? "true" : "false", "aria-label": `Page ${n}`, onclick: () => onGo(n) }, String(n)));
  });
  return h("nav", { class: "pager", "aria-label": "Pages" },
    h("button", { class: "kt-btn", type: "button", disabled: page <= 1, onclick: () => onGo(page - 1) }, "Previous"),
    h("div", { class: "pager__nums" }, out),
    h("button", { class: "kt-btn", type: "button", disabled: page >= pages, onclick: () => onGo(page + 1) }, "Next"));
}

function channelCard(c) {
  const pic = c.source === "plex" ? plexPoster(c.external_id, c.title, "poster--round")
    : chanAvatar(c.external_id, c.thumb_url, c.title, "chan-card__pic");
  const marks = [c.source === "plex" ? "Plex" : null, c.sub_id ? "Subscribed" : null, c.waiting ? `${c.waiting} to approve` : null].filter(Boolean);
  return h("a", { class: "chan-card", href: `#channel/${c.id}` }, pic,
    h("div", { class: "chan-card__title" }, c.title),
    h("div", { class: "kt-muted chan-card__meta" }, `${c.approved} video${c.approved === 1 ? "" : "s"}`),
    marks.length ? h("div", { class: "kt-muted chan-card__meta" }, marks.join(" · ")) : null);
}

function videoCard(it) {
  return h("a", { class: "kt-video kt-video--big linkish", href: `#video/${it.id}` },
    thumb(itemThumb(it), { time: it.duration_s }),
    h("div", { class: "kt-video__body" }, h("div", { class: "kt-video__title" }, it.title), h("div", { class: "kt-muted" }, it.container_title)));
}

async function viewLibrary() {
  const chans = await api("/channels");
  const kids = profiles.filter((p) => p.kind === "child");
  const box = h("div", { class: "kt-stack", style: "gap:16px" });
  const who = h("div", { class: "kt-row" });
  const view = h("div", { class: "seg", role: "group", "aria-label": "Show" });
  const inLibrary = chans.filter((c) => c.approved > 0 || c.sub_id || c.profile_ids.length);
  const onlyWaiting = chans.filter((c) => !inLibrary.includes(c) && c.waiting).length;
  let videos = [], total = 0;

  // One page at a time, numbered (the owner: pages, not "Show more").
  const loadVideos = async (reset) => {
    if (reset) libState.page = 1;
    const r = await api(`/items?approval=approved&total=true&limit=${PAGE}&offset=${(libState.page - 1) * PAGE}` + (libState.who ? `&profile_id=${libState.who}` : ""));
    videos = r.items; total = r.total;
  };
  const draw = () => {
    fill(who, [{ id: 0, name: "Everyone" }, ...kids].map((p) => h("button", { class: "kt-chip", type: "button", "aria-pressed": libState.who === p.id ? "true" : "false",
      onclick: () => run(async () => { libState.who = p.id; if (libState.view === "videos") await loadVideos(true); draw(); }) }, p.name)));
    fill(view, [["channels", "Channels"], ["videos", "Videos"]].map(([v, t]) => h("button", { type: "button", "aria-pressed": libState.view === v ? "true" : "false",
      onclick: () => run(async () => { libState.view = v; if (v === "videos") { fill(box, skelGrid(4)); await loadVideos(true); } draw(); }) }, t)));
    if (libState.view === "channels") {
      const shown = inLibrary.filter((c) => !libState.who || c.seen_by.includes(libState.who));
      fill(box, shown.length ? h("div", { class: "chan-grid" }, shown.map(channelCard))
        : h("div", { class: "empty" }, libState.who ? `Nothing for ${namesOf([libState.who])} yet. Open a channel and choose who can see it.` : "No channels yet."));
    } else {
      fill(box, videos.length ? h("div", { class: "kt-grid" }, videos.map(videoCard)) : h("div", { class: "empty" }, "No approved videos yet."),
        pager(libState.page, Math.ceil(total / PAGE), (n) => run(async () => { libState.page = n; fill(box, skelGrid(4)); await loadVideos(false); draw(); box.scrollIntoView({ block: "start" }); })));
    }
  };

  const addBtn = h("a", { class: "kt-btn kt-btn--primary", href: "#add" }, icon("plus"), "Add");
  if (!chans.length) {
    return screen(wordmark(), { action: addBtn, search: searchForm() },
      h("div", { class: "empty-state" },
        h("h2", { class: "h-display" }, "Nothing here yet"),
        h("p", { style: "margin:0" }, "Search for a channel or video above, or bring in what the boys already watch."),
        h("div", { class: "kt-row", style: "justify-content:center" },
          h("a", { class: "kt-btn kt-btn--primary", href: "#import" }, "Import from YouTube Kids"),
          h("a", { class: "kt-btn", href: "#plex" }, "Browse Plex"))));
  }
  screen(wordmark(), { action: addBtn, search: searchForm() },
    h("div", { class: "kt-row lib-filters" }, who, view),
    box,
    onlyWaiting ? h("a", { class: "kt-banner linkish", href: "#approve" }, h("span", {}, h("strong", {}, `${onlyWaiting} more channel${onlyWaiting > 1 ? "s have" : " has"} videos waiting for your yes. `), "Open Approve →")) : null);
  if (libState.view === "videos") await loadVideos(true);
  draw();
}

// ---- Search results: your library, Plex and YouTube together ------------------------------------------------------

const findCache = { q: "", yt: null };

function plexCard(m, allowed, after) {
  const isOn = allowed.has(m.rating_key);
  return h("div", { class: "poster-card" },
    plexPoster(m.rating_key, m.title),
    h("div", { class: "poster-card__title", title: m.title }, m.title),
    h("div", { class: "kt-muted poster-card__meta" }, [m.type === "collection" ? "Collection" : m.year, m.rating,
      m.count ? `${m.count} ${m.type === "show" ? "episodes" : "items"}` : null].filter(Boolean).join(" · ")),
    isOn ? h("span", { class: "kt-tag kt-tag--ok", style: "align-self:flex-start" }, "Allowed")
      : h("button", { class: "kt-btn kt-btn--quiet poster-card__btn", type: "button", onclick: (e) => run(async () => {
          const ids = forIds();
          busy(e.currentTarget);
          await api("/plex/allow", { method: "POST", body: { rating_key: m.rating_key, profile_ids: ids } });
          allowed.add(m.rating_key);
          toast(`Allowed ${m.title} for ${namesOf(ids)}.`);
          after();
        }) }, "Allow"));
}

async function viewFind(q) {
  const link = /^https?:\/\//i.test(q);
  const lib = h("div", { class: "kt-stack", style: "gap:12px" });
  const plx = h("div", { class: "kt-stack", style: "gap:12px" });
  const yt = h("div", { class: "kt-stack", style: "gap:16px" });
  screen("Search", { back: "library" }, searchForm(q), forRow(), lib, plx, yt);

  if (link) {
    fill(yt, loadingLine("Reading that link on YouTube…"), skelChannel());
    return run(async () => drawListing(yt, await api("/look", { method: "POST", body: { url: q } }))).finally(() => { if (yt.querySelector(".loading-line")) fill(yt); });
  }

  const ql = q.toLowerCase();
  // 1. Your library: straight away.
  run(async () => {
    const [chans, items] = await Promise.all([api("/channels"), api("/items?limit=12&q=" + encodeURIComponent(q))]);
    const hits = chans.filter((c) => c.title.toLowerCase().includes(ql));
    const state = (it) => (it.approval === "waiting" ? h("span", { class: "kt-tag kt-tag--warn" }, "Waiting in Approve")
      : it.approval === "hidden" ? h("span", { class: "kt-tag" }, "Hidden") : it.status !== "ready" ? h("span", { class: "kt-tag" }, "Downloading") : null);
    fill(lib, h("h2", { class: "kt-label" }, "In your library"),
      hits.length || items.length ? [
        hits.length ? h("div", { class: "chan-grid" }, hits.map(channelCard)) : null,
        items.length ? h("div", { class: "vgrid" }, items.map((it) => videoRow(it, { onOpen: () => go(`video/${it.id}`), right: state(it) }))) : null]
        : h("div", { class: "kt-muted" }, "Nothing you already have matches."));
  });
  // 2. Plex: quick, and only if it is connected.
  run(async () => {
    const st = await api("/plex").catch(() => ({ connected: false }));
    if (!st.connected) return;
    const allowed = new Set((st.allowed || []).map((a) => a.external_id));
    const found = await api("/plex/search?q=" + encodeURIComponent(q));
    const draw = () => fill(plx, h("h2", { class: "kt-label" }, "In Plex"),
      found.length ? h("div", { class: "poster-grid" }, found.slice(0, 18).map((m) => plexCard(m, allowed, draw))) : h("div", { class: "kt-muted" }, "Nothing in Plex matches."));
    draw();
  });
  // 3. YouTube: a few seconds. Kept, so coming back from a video does not search again.
  // "Show more" asks for the top 15 more than last time and keeps the videos not shown yet: YouTube reshuffles
  // between two searches, so "results 16 to 30" repeated about half of the first 15. Whether there are more is
  // judged by YouTube filling the whole top, not by how many were new.
  const PAGE = 15;
  const drawYt = () => {
    const c = findCache;
    fill(yt, h("h2", { class: "kt-label" }, "On YouTube"));
    const box = h("div", { class: "kt-stack", style: "gap:16px" });
    yt.append(box);
    drawResults(box, c.yt);
    if (c.more && c.yt.length) yt.append(h("button", { class: "kt-btn", type: "button", style: "align-self:center", onclick: (e) => run(async () => {
      const btn = e.currentTarget;
      busy(btn);
      btn.textContent = "Looking for more…";
      try {
        const want = c.asked + PAGE;
        const top = await api(`/search?q=${encodeURIComponent(q)}&limit=${want}`);
        const have = new Set(c.yt.map((v) => v.external_id));
        c.yt = c.yt.concat(top.filter((v) => !have.has(v.external_id)));
        c.asked = want;
        c.more = top.length === want && want < 300;
      } finally { busy(btn, false); }
      if (location.hash === "#find/" + encodeURIComponent(q)) { const y = window.scrollY; drawYt(); window.scrollTo(0, y); }
    }) }, "Show more from YouTube"));
    else if (c.yt.length >= PAGE) yt.append(h("div", { class: "kt-muted", style: "text-align:center" }, "That's all YouTube shows for this search."));
  };
  if (findCache.q === q && findCache.yt) return drawYt();
  fill(yt, h("h2", { class: "kt-label" }, "On YouTube"), loadingLine(`Searching YouTube for “${q}”…`), h("div", { class: "vgrid" }, skelRows(4)));
  run(async () => {
    const videos = await api("/search?q=" + encodeURIComponent(q));
    Object.assign(findCache, { q, yt: videos, asked: PAGE, more: videos.length === PAGE });
    if (location.hash === "#find/" + encodeURIComponent(q)) drawYt();
  }).finally(() => { if (yt.querySelector(".loading-line")) fill(yt, h("h2", { class: "kt-label" }, "On YouTube"), h("div", { class: "kt-muted" }, "YouTube didn't answer. Try again.")); });
}

function drawResults(el, videos) {
  if (!videos.length) return fill(el, h("div", { class: "kt-muted" }, "Nothing found on YouTube."));
  const chans = [];
  const seen = new Set();
  for (const v of videos) if (v.channel_id && !seen.has(v.channel_id)) { seen.add(v.channel_id); chans.push(v); }
  fill(el,
    chans.length ? h("nav", { class: "kt-strip", "aria-label": "Channels in these results" }, chans.slice(0, 8).map((v) =>
      h("a", { href: "#subscribe/" + encodeURIComponent(`https://www.youtube.com/channel/${v.channel_id}`) },
        v.channel_pic ? chanAvatar(v.channel_id, "", v.channel_title, "kt-avatar--lg") : laterAvatar(v.channel_id, v.channel_title, "kt-avatar--lg"), v.channel_title))) : null,
    chans.length ? h("div", { class: "kt-muted", style: "margin-top:-8px" }, "Tap a channel to look at it and subscribe.") : null,
    h("div", { class: "vgrid" }, videos.map((v) => videoRow(v, { right: addButtons(v) }))));
  watchPictures(el);
}

function drawListing(el, l) {
  const head = l.is_channel
    ? h("div", { class: "panel" },
        h("div", { class: "kt-channel" }, chanAvatar(l.channel_pic ? l.channel_id : "", l.avatar_url, l.title, "kt-avatar--lg"),
          h("div", { class: "kt-video__body" }, h("div", { class: "kt-video__title" }, l.title), h("div", { class: "kt-muted" }, `${l.videos.length} recent videos`))),
        h("a", { class: "kt-btn kt-btn--primary", href: "#subscribe/" + encodeURIComponent(l.url), style: "align-self:flex-start" }, "Subscribe to this channel"))
    : l.kind === "list" ? h("h2", { class: "kt-label" }, l.title || "Playlist") : null;
  const left = l.videos.filter((v) => !v.in_library);
  const addAll = l.kind === "list" && left.length
    ? h("button", { class: "kt-btn", type: "button", style: "align-self:flex-start", onclick: (e) => run(async () => {
        const ids = forIds();
        if (!ids.length) throw new Error("Choose who it's for first, at the top.");
        busy(e.currentTarget);
        const r = await api("/add", { method: "POST", body: { urls: left.map((v) => v.url), approve: true, profile_ids: ids } });
        toast(`Added ${r.added.length} videos for ${namesOf(ids)}. They download one at a time.`);
        kickActivity();
        l.videos.forEach((v) => (v.in_library = true));
        drawListing(el, l);
      }) }, `Add all ${left.length}`)
    : null;
  fill(el, head, addAll, h("div", { class: "vgrid" }, l.videos.map((v) => videoRow(v, { right: addButtons(v) }))));
}

// ---- Add: every way to bring something in, in one list --------------------------------------------------------------

async function viewAddMenu() {
  const [plex, ai, open] = await Promise.all([api("/plex").catch(() => ({ connected: false })), api("/ai").catch(() => ({})), api("/imports/open").catch(() => ({}))]);
  const way = (title, sub, value, hash) => h("a", { class: "kt-list__row", href: "#" + hash },
    h("span", { class: "kt-list__text" }, title, h("span", { class: "kt-muted" }, sub)), h("span", { class: "kt-list__value" }, value || "›"));
  screen("Add", { back: "library", narrow: true },
    h("h2", { class: "kt-label" }, "Search or paste a link"),
    searchForm(),
    h("p", { class: "kt-muted", style: "margin:0" }, "Type a name to search your library, YouTube and Plex together. Or paste a YouTube link to a video, a playlist or a channel."),
    h("h2", { class: "kt-label" }, "Other ways"),
    h("div", { class: "kt-list" },
      way("Browse Plex", plex.connected ? "Allow shows and movies you already own" : "Connect Plex first, in Settings", plex.connected ? `${(plex.allowed || []).length} allowed` : "Not connected", plex.connected ? "plex" : "plex-connect"),
      way("Import from YouTube Kids", "Paste links, a Google Takeout file or a playlist", open.state === "review" ? "Ready to review" : open.id ? "In progress" : null, open.state === "review" ? `import/${open.id}` : "import"),
      way("Ideas from the AI", ai.enabled ? "Channels and videos it thinks the boys would like" : "Off. Turn it on in Settings › AI", ai.enabled ? (ai.new_suggestions ? `${ai.new_suggestions} new` : "None yet") : "Off", ai.enabled ? "ideas" : "ai")));
  document.getElementById("q")?.focus();
}

async function viewSubscribe(url, subId) {
  let sub = null, info = null;
  if (subId) {
    const ch = await api(`/channels/${subId}`);
    sub = ch.subscription;
    info = { title: ch.channel.title, avatar_url: ch.channel.thumb_url, channel_id: ch.channel.source === "local" ? ch.channel.external_id : "", url: ch.channel.url, profile_ids: ch.profile_ids, trusted: !!ch.channel.trusted };
  } else {
    screen("Subscribe", { back: "library" }, skelChannel(), loadingLine("Reading the channel on YouTube…"), skelRows(3));
    const l = await api("/look", { method: "POST", body: { url } });
    info = { title: l.title, avatar_url: l.avatar_url, channel_id: l.channel_id, url: l.url || url, videos: l.videos, profile_ids: profiles.filter((p) => p.kind === "child").map((p) => p.id), trusted: false };
  }
  const r = sub || { mode: "new", last_n: 10, min_s: 0, max_s: 0, skip_shorts: 1, skip_live: 1, title_must: "", title_not: "", check_hours: 6, daily_cap: 10, keep_mode: "all", keep_n: 30, keep_days: 60, active: 1 };
  let pids = info.profile_ids, trusted = info.trusted;
  const sel = (id, value, options) => h("select", { id, class: "kt-input" }, options.map(([v, t]) => h("option", { value: v, selected: String(v) === String(value) }, t)));
  const num = (id, value) => h("input", { id, class: "kt-input num", type: "number", min: 0, value });
  const f = {
    mode: sel("mode", r.mode, [["new", "New uploads only"], ["last", "The latest few"], ["all", "Everything"]]),
    last_n: num("last_n", r.last_n),
    min: num("min", Math.round(r.min_s / 60)),
    max: num("max", Math.round(r.max_s / 60)),
    title_not: h("input", { id: "title_not", class: "kt-input", value: r.title_not, placeholder: "unboxing, toy" }),
    title_must: h("input", { id: "title_must", class: "kt-input", value: r.title_must, placeholder: "" }),
    keep_mode: sel("keep_mode", r.keep_mode, [["all", "Everything"], ["last", "Only the latest"], ["watched", "Delete once both watched"]]),
    keep_n: num("keep_n", r.keep_n),
    keep_days: num("keep_days", r.keep_days),
    check_hours: num("check_hours", r.check_hours),
    daily_cap: num("daily_cap", r.daily_cap),
  };
  let shorts = !!r.skip_shorts, live = !!r.skip_live;
  const rules = () => ({
    mode: f.mode.value, last_n: +f.last_n.value || 10, min_s: (+f.min.value || 0) * 60, max_s: (+f.max.value || 0) * 60,
    skip_shorts: shorts, skip_live: live, title_must: f.title_must.value, title_not: f.title_not.value,
    check_hours: +f.check_hours.value || 6, daily_cap: +f.daily_cap.value || 10,
    keep_mode: f.keep_mode.value, keep_n: +f.keep_n.value || 30, keep_days: +f.keep_days.value || 60, active: true,
  });
  const strip = (info.videos || []).slice(0, 3);
  const save = h("button", { class: "kt-btn kt-btn--primary kt-btn--wide", type: "button", onclick: (e) => run(async () => {
    busy(e.target);
    if (subId) {
      if (sub) await api(`/subscriptions/${sub.id}`, { method: "PUT", body: rules() });
      await api(`/channels/${subId}`, { method: "PATCH", body: { trusted, profile_ids: pids } });
      if (!sub) await api("/subscribe", { method: "POST", body: { url: info.url, rules: rules(), profile_ids: pids, trusted } });
      toast("Saved");
      go(`channel/${subId}`);
    } else {
      const res = await api("/subscribe", { method: "POST", body: { url: info.url, rules: rules(), profile_ids: pids, trusted } });
      toast(`Subscribed for ${namesOf(pids)}. New videos ${trusted ? "are approved on arrival" : "will wait in Approve"}.`);
      kickActivity();
      go(`channel/${res.container_id}`);
    }
  }).finally(() => busy(e.target, false)) }, subId && sub ? "Save" : "Subscribe");
  screen(subId && sub ? "Subscription" : "Subscribe", { back: subId ? `channel/${subId}` : "library" },
    h("div", { class: "kt-channel" }, chanAvatar(info.channel_id, info.avatar_url, info.title, "kt-avatar--lg"),
      h("div", { class: "kt-video__body" }, h("div", { class: "kt-video__title" }, info.title), h("div", { class: "kt-muted" }, info.url))),
    strip.length ? h("div", { class: "kt-row", style: "flex-wrap:nowrap; gap:6px" }, strip.map((v) => thumb(v.thumb_url, { style: "width:33%; border-radius:var(--radius-sm)" }))) : null,
    h("h2", { class: "kt-label" }, "Who can see this channel"),
    profileChips(pids, (next) => (pids = next)),
    h("div", { class: "kt-list" },
      row("Approve new videos without asking", switchBtn(trusted, "Approve without asking", (v) => (trusted = v)), "Off: each new video waits in Approve. Blocked words always wait.")),
    subId && sub ? null : [h("p", { class: "kt-muted", style: "margin:0" }, "As it stands: new uploads only, no Shorts or live streams, checked every 6 hours, everything kept."), save],
    h("details", { class: "more-opts", open: subId && sub ? true : null }, h("summary", {}, "More options"),
      h("div", { class: "kt-stack", style: "padding-top:12px" },
        h("h2", { class: "kt-label" }, "What to download"),
        h("div", { class: "kt-list" },
          row(h("label", { for: "mode" }, "Which videos"), f.mode),
          row(h("label", { for: "last_n" }, "How many of the latest"), f.last_n, "Only for “The latest few”"),
          row(h("label", { for: "min" }, "Shortest, in minutes"), f.min),
          row(h("label", { for: "max" }, "Longest, in minutes"), f.max, "0 means no limit"),
          row("Skip Shorts", switchBtn(shorts, "Skip Shorts", (v) => (shorts = v))),
          row("Skip live streams", switchBtn(live, "Skip live streams", (v) => (live = v))),
          row(h("label", { for: "title_not" }, "Leave out titles with"), f.title_not),
          row(h("label", { for: "title_must" }, "Only titles with"), f.title_must, "Optional. Commas between words")),
        h("h2", { class: "kt-label" }, "Keeping"),
        h("div", { class: "kt-list" },
          row(h("label", { for: "keep_mode" }, "Keep"), f.keep_mode),
          row(h("label", { for: "keep_n" }, "How many to keep"), f.keep_n, "For “Only the latest”"),
          row(h("label", { for: "keep_days" }, "Days after watching"), f.keep_days, "For “Delete once both watched”")),
        h("h2", { class: "kt-label" }, "Checking"),
        h("div", { class: "kt-list" },
          row(h("label", { for: "check_hours" }, "Check every (hours)"), f.check_hours),
          row(h("label", { for: "daily_cap" }, "Most downloads a day"), f.daily_cap, "Keeps big first imports gentle")))),
    subId && sub ? save : null,
    subId && sub ? h("button", { class: "kt-btn kt-btn--danger", type: "button", style: "align-self:flex-start", onclick: () => run(async () => {
      const r = await api(`/subscriptions/${sub.id}`, { method: "DELETE" });
      toast(r.stopped ? `Unsubscribed. ${r.stopped} waiting download${r.stopped === 1 ? "" : "s"} stopped; downloaded videos stay.` : "Unsubscribed. Downloaded videos stay.");
      go(`channel/${subId}`);
    }) }, "Unsubscribe") : null);
}

// ---- Approve: videos waiting for a parent's yes (ADR 0037; was "Inbox") --------------------------------------------

// Who can see one video. Names that come from its channel are shown on, and changed on the channel.
function itemWhoChips(it) {
  const fromChannel = new Set(it.channel_profile_ids);
  const mine = new Set(it.item_profile_ids);
  return h("div", { class: "kt-row" }, profiles.map((p) => {
    const viaChannel = fromChannel.has(p.id);
    return h("button", { class: "kt-chip", type: "button", "aria-pressed": viaChannel || mine.has(p.id) ? "true" : "false", disabled: viaChannel,
      title: viaChannel ? "Set on the channel" : null,
      onclick: (e) => run(async () => {
        const on = !mine.has(p.id);
        const btn = e.currentTarget;
        await api("/assign", { method: "POST", body: { profile_id: p.id, item_id: it.id, on } });
        on ? mine.add(p.id) : mine.delete(p.id);
        btn.setAttribute("aria-pressed", String(on));
      }) }, p.name);
  }));
}

let approveKeys = null;

async function viewApprove() {
  let items = await api("/items?approval=waiting&hide_failed=1&limit=500");
  let selected = null;
  setApproveDot(items.length);
  const list = h("div", { class: "approve__list" });
  const detail = h("div", { class: "approve__detail" });

  const remove = (ids) => {
    const at = items.findIndex((x) => x.id === selected);
    items = items.filter((x) => !ids.includes(x.id));
    setApproveDot(items.length);
    if (ids.includes(selected)) selected = items.length ? items[Math.min(at, items.length - 1)].id : null;
    draw();
  };
  const decide = (its, approval, msg) => run(async () => {
    const ids = its.map((x) => x.id);
    if (!ids.length) return;
    await api("/items/decide", { method: "POST", body: { ids, approval } });
    toast(msg);
    remove(ids);
  });
  const approve = (it) => decide([it], "approved", "Approved. The boys can watch it" + (it.status === "ready" ? " now." : " once it has downloaded."));
  const refuse = (it) => decide([it], "hidden", "Not for them. It's hidden; you can find it again by searching.");

  const select = (it) => {
    if (!isWide()) return go(`video/${it.id}`);
    selected = it.id;
    draw();
  };

  const rowOf = (it) => h("div", { class: "approve-row" + (it.id === selected ? " approve-row--on" : ""), "data-id": it.id },
    thumb(itemThumb(it), { time: it.duration_s, onclick: () => select(it) }),
    h("div", { class: "kt-video__body" },
      h("div", { class: "kt-video__title clickable", onclick: () => select(it) }, it.title),
      h("div", { class: "kt-muted" }, [ago(it.added_at), it.status !== "ready" ? "still downloading" : null].filter(Boolean).join(" · ")),
      it.blocked_reason ? h("span", { class: "kt-tag kt-tag--bad", style: "align-self:flex-start" }, it.blocked_reason) : null,
      h("div", { class: "kt-row approve-row__btns" },
        h("button", { class: "kt-btn kt-btn--sm" + (it.blocked_reason ? "" : " kt-btn--primary"), type: "button", onclick: () => approve(it) }, it.blocked_reason ? "Approve anyway" : "Approve"),
        h("button", { class: "kt-btn kt-btn--sm", type: "button", onclick: () => refuse(it) }, "Not for them"))));

  const drawDetail = () => {
    const it = items.find((x) => x.id === selected);
    if (!it) return fill(detail, h("div", { class: "empty" }, items.length ? "Choose a video on the left to watch it here." : ""));
    const player = h("div", { class: "approve-player" }, itemThumb(it) ? h("img", { src: itemThumb(it), alt: "" }) : null,
      it.source === "local" && it.external_id ? h("button", { class: "approve-player__play", type: "button", "aria-label": "Play a preview",
        onclick: () => fill(player, preview(it.external_id)) }, icon("play")) : null);
    const who = h("div", {}, loadingLine("…"));
    fill(detail,
      player,
      h("div", { class: "kt-video__title", style: "font-size:18px; line-height:24px; -webkit-line-clamp:3" }, it.title),
      h("a", { class: "kt-muted linkish", href: `#channel/${it.container_id}` }, [it.container_title, it.upload_date, mins(it.duration_s)].filter(Boolean).join(" · ")),
      it.blocked_reason ? h("div", { class: "kt-banner kt-banner--bad" }, h("span", {}, h("strong", {}, it.blocked_reason), ". Look before you approve it.")) : null,
      h("div", { class: "kt-row", style: "flex-wrap:nowrap" },
        h("button", { class: "kt-btn kt-btn--primary", type: "button", style: "flex:1", onclick: () => approve(it) }, "Approve", h("kbd", {}, "A")),
        h("button", { class: "kt-btn", type: "button", style: "flex:1", onclick: () => refuse(it) }, "Not for them", h("kbd", {}, "X"))),
      h("h2", { class: "kt-label" }, "Who can see it"), who,
      h("a", { class: "kt-btn kt-btn--quiet", href: `#video/${it.id}`, style: "align-self:flex-start" }, "Everything about this video"));
    api(`/items/${it.id}/detail`).then((d) => { if (selected === it.id) fill(who, itemWhoChips(d)); }).catch(() => fill(who));
  };

  const draw = () => {
    if (isWide() && selected == null && items.length) selected = items[0].id;
    const groups = new Map();
    for (const it of items) (groups.get(it.container_id) || groups.set(it.container_id, []).get(it.container_id)).push(it);
    fill(list, items.length ? [...groups.values()].map((its) => {
      const first = its[0], clean = its.filter((x) => !x.blocked_reason);
      const local = first.container_source === "local";
      return h("section", { class: "approve-group" },
        h("div", { class: "approve-group__head" },
          h("a", { class: "kt-channel linkish", href: `#channel/${first.container_id}` },
            local ? chanAvatar(first.container_external_id, first.container_thumb, first.container_title) : avatar(first.container_thumb, first.container_title, "kt-avatar--plain"),
            h("div", { class: "kt-video__body" }, h("div", { class: "kt-video__title" }, first.container_title),
              h("div", { class: "kt-muted" }, `${its.length} waiting`))),
          its.length > 1 ? h("div", { class: "kt-row", style: "gap:8px; flex-wrap:wrap; justify-content:flex-end" },
            clean.length > 1 ? h("button", { class: "kt-btn kt-btn--sm", type: "button", onclick: () => decide(clean, "approved", `Approved ${clean.length} from ${first.container_title}`) }, `Approve all ${clean.length}`) : null,
            // The other answer for the whole channel. Two taps: it also stops their downloads.
            h("button", { class: "kt-btn kt-btn--sm kt-btn--quiet", type: "button", onclick: (e) => {
              const b = e.currentTarget;
              if (!b.dataset.sure) { b.dataset.sure = "1"; b.textContent = `Tap again: none of these ${its.length}`; return; }
              decide(its, "hidden", `${its.length} from ${first.container_title}: not for them`);
            } }, `Not for them, all ${its.length}`)) : null),
        its.map(rowOf),
        local && !first.container_trusted ? h("button", { class: "kt-btn kt-btn--quiet approve-group__always", type: "button", onclick: (e) => {
          const b = e.currentTarget;
          if (!b.dataset.sure) { b.dataset.sure = "1"; b.textContent = `Tap again: new ${first.container_title} videos will skip this list`; return; }
          run(async () => {
            await api(`/channels/${first.container_id}`, { method: "PATCH", body: { trusted: true } });
            if (clean.length) await api("/items/decide", { method: "POST", body: { ids: clean.map((x) => x.id), approval: "approved" } });
            toast(`${first.container_title} is always approved from now on.`);
            remove(clean.map((x) => x.id));
          });
        } }, "Always approve this channel") : null);
    }) : h("div", { class: "empty-state" }, h("h2", { class: "h-display" }, "Nothing is waiting"),
      h("p", { style: "margin:0" }, "When a channel you follow posts something new, it shows up here first, unless you set that channel to always approve.")));
    drawDetail();
  };

  screen("Approve", {},
    h("p", { style: "margin:0" }, "New videos wait here until you say yes. The boys can't see them until then."),
    h("div", { class: "approve" }, list, detail));
  draw();

  // Keys, on a computer: up and down move, A approves, X says no.
  document.removeEventListener("keydown", approveKeys);
  approveKeys = (e) => {
    if (!location.hash.startsWith("#approve") || !isWide() || e.target.closest("input, textarea, select") || e.metaKey || e.ctrlKey || e.altKey) return;
    const i = items.findIndex((x) => x.id === selected);
    const it = items[i];
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      const next = items[i + (e.key === "ArrowDown" ? 1 : -1)];
      if (next) { e.preventDefault(); selected = next.id; draw(); list.querySelector(`[data-id="${next.id}"]`)?.scrollIntoView({ block: "nearest" }); }
    } else if (it && e.key.toLowerCase() === "a") approve(it);
    else if (it && e.key.toLowerCase() === "x") refuse(it);
  };
  document.addEventListener("keydown", approveKeys);
}

async function setApproveDot(n) {
  if (n === undefined) n = (await api("/items?approval=waiting&hide_failed=1&limit=1000").catch(() => [])).length;
  const dot = document.getElementById("approve-dot");
  dot.textContent = n;
  dot.hidden = !n;
}

// ---- Library and channels ----------------------------------------------------------------------------------------

const chanPage = { key: "", page: 1 };

async function viewChannel(id, tab = "library") {
  const d = await api(`/channels/${id}`);
  if (chanPage.key !== `${id}/${tab}`) Object.assign(chanPage, { key: `${id}/${tab}`, page: 1 });
  const c = d.channel;
  const waiting = d.items.filter((it) => it.approval === "waiting" && it.status !== "failed");
  const approved = d.items.filter((it) => it.approval === "approved");
  const shown = tab === "waiting" ? waiting : approved;
  const sub = d.subscription, local = c.source === "local";
  let pids = d.profile_ids;
  const tags = [
    !local ? h("span", { class: "kt-tag" }, "From Plex") : null,
    sub ? h("span", { class: "kt-tag kt-tag--ok" }, sub.mode === "new" ? "Subscribed: new videos come in" : "Subscribed") : null,
    local && c.trusted ? h("span", { class: "kt-tag kt-tag--ok" }, "Always approved") : local && sub ? h("span", { class: "kt-tag" }, "New videos wait for your yes") : null,
    sub && sub.last_error ? h("span", { class: "kt-tag kt-tag--warn", title: sub.last_error }, "Last check failed") : null,
  ];
  screen(c.title, { back: "library" },
    h("div", { class: "chan-head" },
      local ? chanAvatar(c.external_id, c.thumb_url, c.title, "big-avatar") : plexPoster(c.external_id, c.title, "poster--round big-avatar"),
      h("div", { class: "kt-stack", style: "gap:8px; flex:1; min-width:0" },
        h("div", { class: "kt-muted" }, `${approved.length} approved${waiting.length ? ` · ${waiting.length} waiting` : ""}`),
        h("div", { class: "kt-row" }, tags),
        h("div", { class: "kt-row" },
          local ? h("a", { class: "kt-btn" + (sub ? "" : " kt-btn--primary"), href: `#channel-settings/${id}` }, sub ? "Subscription settings" : "Subscribe") : null,
          sub ? h("button", { class: "kt-btn", type: "button", onclick: (e) => run(async () => {
            busy(e.currentTarget);
            const r = await api(`/subscriptions/${sub.id}/check`, { method: "POST" });
            toast(r.error ? r.error : r.queued ? `Found ${r.queued} new. Downloading.` : "Nothing new.");
            kickActivity();
            viewChannel(id, tab);
          }) }, "Check for new videos") : null))),
    h("h2", { class: "kt-label" }, "Who can see this channel"),
    profileChips(pids, (next) => run(async () => { pids = next; await api(`/channels/${id}`, { method: "PATCH", body: { profile_ids: next } }); toast(`${c.title}: ${next.length ? "for " + namesOf(next) : "nobody for now"}`); })),
    h("nav", { class: "kt-tabs", "aria-label": "Videos" },
      h("a", { href: `#channel/${id}`, "aria-current": tab === "library" ? "page" : null }, `Approved ${approved.length || ""}`.trim()),
      h("a", { href: `#channel/${id}/waiting`, "aria-current": tab === "waiting" ? "page" : null }, `Waiting ${waiting.length || ""}`.trim())),
    shown.length ? h("div", { class: "kt-grid" }, shown.slice((chanPage.page - 1) * PAGE, chanPage.page * PAGE).map((it) =>
      h("a", { class: "kt-video kt-video--big linkish", href: `#video/${it.id}` },
        thumb(it.has_thumb ? `/api/admin/items/${it.id}/thumb` : it.thumb_url, { time: it.duration_s }),
        h("div", { class: "kt-video__title" }, it.title),
        it.status !== "ready" ? h("span", { class: "kt-tag" + (it.status === "failed" ? " kt-tag--bad" : ""), style: "align-self:flex-start" }, it.play_note || (it.status === "failed" ? "Download failed" : "Downloading")) : null)))
      : h("div", { class: "empty" }, tab === "waiting" ? "Nothing waiting." : sub ? "No approved videos yet. New ones will show up here." : "No approved videos yet."),
    pager(chanPage.page, Math.ceil(shown.length / PAGE), (n) => { chanPage.page = n; viewChannel(id, tab).then(() => window.scrollTo(0, 0)); }),
    tab === "waiting" && waiting.length ? h("a", { class: "kt-btn", href: "#approve", style: "align-self:flex-start" }, "Go through them in Approve") : null);
}

// ---- One video ----------------------------------------------------------------------------------------------------

async function viewVideo(id) {
  const it = await api(`/items/${id}/detail`);
  const prev = h("div");
  const fromChannel = new Set(it.channel_profile_ids);
  const whoChips = itemWhoChips(it);
  const tagInput = h("input", { class: "kt-input inline-input", placeholder: "add a tag", "aria-label": "Add a tag" });
  const segRows = it.segments.map((s) => row(`${mins(s.start_s) || "0:00"} to ${mins(s.end_s)}`, h("button", { class: "kt-btn kt-btn--danger", type: "button", onclick: () => run(async () => {
    await api(`/segments/${s.id}`, { method: "DELETE" });
    viewVideo(id);
  }) }, "Remove"), s.category === "parent" ? "Added by you" : s.category));
  const segFrom = h("input", { class: "kt-input inline-input", placeholder: "from 1:20", "aria-label": "Skip from" });
  const segTo = h("input", { class: "kt-input inline-input", placeholder: "to 2:05", "aria-label": "Skip to" });
  const toSec = (t) => t.split(":").reduce((a, b) => a * 60 + (+b || 0), 0);
  const skipped = it.segments.reduce((a, s) => a + (s.end_s - s.start_s), 0);
  const blocked = Object.entries(it.why).filter(([, steps]) => steps.some((s) => !s.ok));
  screen("Video", { back: "library", action: it.source === "local" && it.external_id ? h("button", { class: "kt-btn kt-btn--quiet", type: "button", onclick: () => fill(prev, preview(it.external_id)) }, "Preview") : null },
    prev,
    h("div", { class: "kt-video kt-video--big" },
      h("div", { class: "kt-thumb" }, (it.has_thumb || it.thumb_url) ? h("img", { src: it.has_thumb ? `/api/admin/items/${it.id}/thumb` : it.thumb_url, alt: "" }) : null, h("span", { class: "kt-thumb__time" }, mins(it.duration_s))),
      h("div", { class: "kt-video__meta" },
        avatar(it.container_thumb, it.container_title, "kt-avatar--plain"),
        h("div", { class: "kt-video__body" },
          h("div", { class: "kt-video__title", style: "font-size:17px; line-height:23px; -webkit-line-clamp:3" }, it.title),
          h("a", { class: "kt-muted linkish", href: `#channel/${it.container_id}` }, [it.container_title, it.upload_date].filter(Boolean).join(" · "))))),
    it.blocked_reason ? h("div", { class: "kt-banner kt-banner--bad" }, h("span", {}, h("strong", {}, it.blocked_reason), ". It waits in Approve until you decide.")) : null,
    it.play_note ? h("div", { class: "kt-banner kt-banner--warn" }, h("span", {}, h("strong", {}, "Won't play on the TVs: "), it.play_note)) : null,
    it.job && it.job.state === "failed" ? h("div", { class: "kt-banner kt-banner--bad" }, h("span", {}, h("strong", {}, "Download failed. "), it.job.error.slice(0, 200))) : null,
    h("div", { class: "kt-row", style: "flex-wrap:nowrap" },
      h("button", { class: "kt-btn" + (it.approval === "approved" ? "" : " kt-btn--primary"), type: "button", style: "flex:1", disabled: it.approval === "approved",
        onclick: () => run(async () => { await api(`/items/${id}`, { method: "PATCH", body: { approval: "approved" } }); toast("Approved"); setApproveDot(); viewVideo(id); }) },
        it.approval === "approved" ? "Approved" : "Approve"),
      h("button", { class: "kt-btn", type: "button", style: "flex:1", disabled: it.approval === "hidden",
        onclick: () => run(async () => { await api(`/items/${id}`, { method: "PATCH", body: { approval: "hidden" } }); toast("Hidden from the boys"); setApproveDot(); viewVideo(id); }) },
        it.approval === "hidden" ? "Hidden from the boys" : "Hide from the boys")),
    h("h2", { class: "kt-label" }, "Who can see it"),
    whoChips,
    fromChannel.size ? h("p", { class: "kt-muted", style: "margin:0" }, "Greyed names come from the channel. Change them on the channel.") : null,
    h("h2", { class: "kt-label" }, "Tags"),
    h("div", { class: "kt-row" },
      it.tags.map((t) => h("button", { class: "kt-chip", type: "button", title: "Remove", onclick: () => run(async () => {
        await api("/tag", { method: "POST", body: { target_type: "item", target_id: it.id, tag: t, on: false } });
        viewVideo(id);
      }) }, `${t} ×`)),
      h("form", { onsubmit: (e) => { e.preventDefault(); if (!tagInput.value.trim()) return; run(async () => {
        await api("/tag", { method: "POST", body: { target_type: "item", target_id: it.id, tag: tagInput.value } });
        viewVideo(id);
      }); } }, tagInput)),
    h("h2", { class: "kt-label" }, "Parts to skip"),
    h("div", { class: "kt-list" },
      segRows.length ? segRows : row("Nothing skipped", null),
      row(h("span", { class: "kt-row", style: "flex-wrap:nowrap" }, segFrom, segTo), h("button", { class: "kt-btn kt-btn--quiet", type: "button", onclick: () => run(async () => {
        await api(`/items/${id}/segments`, { method: "POST", body: { start_s: toSec(segFrom.value), end_s: toSec(segTo.value) } });
        viewVideo(id);
      }) }, "Skip"))),
    skipped ? h("p", { class: "kt-muted", style: "margin:0" }, `Plays as ${mins(it.duration_s - skipped)}.`) : null,
    blocked.length ? [h("h2", { class: "kt-label" }, "Why some can't see it"),
      h("div", { class: "kt-list" }, blocked.map(([name, steps]) => row(name, null, steps.filter((s) => !s.ok).map((s) => s.reason).join(" "))))] : null,
    h("div", { class: "kt-row" },
      h("button", { class: "kt-btn kt-btn--danger", type: "button", onclick: (e) => {
        const b = e.currentTarget;
        if (b.dataset.sure) return run(async () => { await api(`/items/${id}`, { method: "DELETE" }); toast("Deleted"); go("library"); });
        b.dataset.sure = "1";
        b.textContent = it.source === "plex" ? "Tap again to forget it (Plex keeps the file)" : "Tap again to delete the file";
      } }, it.source === "plex" ? "Forget" : "Delete")));
}

// ---- Kids: now playing, time left, actions ------------------------------------------------------------------------

// Everything a parent does for one boy right now: what he is watching, his time, and the quick actions.
function kidCard({ profile: p, time: t, reason, playing }, redraw, { link = true } = {}) {
  const act = (action, minutes) => run(async () => {
    await api(`/kids/${p.id}/${action}`, { method: "POST", body: { minutes: minutes || 0 } });
    toast({ extra: `+${minutes} min for ${p.name}`, limit: `${minutes} min limit started for ${p.name}`, lastone: "Last one, then it stops", lock: `Stopped for ${p.name}`, unlock: `Unlocked for ${p.name} until tomorrow`, "clear-limit": "Limit cleared" }[action] || "Done");
    redraw();
  });
  const leftLine = t.limited
    ? h("div", { class: "kt-stack", style: "gap:6px" },
        h("div", { class: "kt-row", style: "justify-content:space-between" }, h("strong", {}, t.open ? `${minutesText(t.left_s)} left` : (reason || "Closed")), h("span", { class: "kt-muted" }, t.open ? reason : `${minutesText(t.used_today_s)} watched today`)),
        t.open ? h("div", { class: "kt-bar kt-bar--time" + (t.left_s < 300 ? " kt-bar--low" : ""), role: "progressbar", "aria-label": "Time left", "aria-valuenow": Math.round(t.left_s / 60), "aria-valuemin": 0 },
          h("i", { style: `width:${Math.min(100, t.daily_s ? (t.left_s / t.daily_s) * 100 : 50)}%` })) : null)
    : h("div", { class: "kt-muted" }, `${minutesText(t.used_today_s)} watched today · ${t.unlocked ? "unlocked until tomorrow" : "no limit running"}`);
  const head = [profileAvatar(p, "kt-avatar--lg"),
    h("div", { class: "kt-video__body" }, h("div", { class: "kt-video__title", style: "font-size:18px" }, p.name), h("div", { class: "kt-muted" }, playing ? `Watching on ${playing.tv}` : "Not watching")),
    link ? h("span", { class: "kt-list__value", "aria-hidden": "true" }, "›") : null];
  return h("div", { class: "panel kid-card" },
    link ? h("a", { class: "kt-channel linkish", href: `#kid/${p.id}` }, head) : h("div", { class: "kt-channel" }, head),
    playing ? h("div", { class: "kt-video" },
      thumb(playing.has_thumb ? `/api/admin/items/${playing.item_id}/thumb` : playing.thumb_url, { style: "width:120px", seen: playing.duration_s ? playing.last_position_s / playing.duration_s : 0 }),
      h("div", { class: "kt-video__body" }, h("div", { class: "kt-video__title" }, playing.title), h("div", { class: "kt-muted" }, `${mins(playing.last_position_s)} of ${mins(playing.duration_s)}${playing.last_state === "paused" ? " · paused" : ""}`))) : null,
    leftLine,
    h("div", { class: "kt-row" },
      t.open && !t.lastone ? h("button", { class: "kt-btn kt-btn--primary", type: "button", onclick: () => act("lastone") }, "Last one") : null,
      t.lastone ? h("span", { class: "kt-tag kt-tag--warn" }, "Last one") : null,
      h("button", { class: "kt-btn", type: "button", onclick: () => act("extra", 10) }, "+10 min"),
      t.open ? h("button", { class: "kt-btn", type: "button", onclick: () => act("lock") }, "End now") : h("button", { class: "kt-btn", type: "button", onclick: () => act("unlock") }, "Unlock")),
    h("div", { class: "kt-row" }, h("span", { class: "kt-muted" }, "Start a limit:"),
      [5, 10, 15, 30, 45, 60].map((m) => h("button", { class: "kt-chip", type: "button", onclick: () => act("limit", m) }, `${m} min`))),
    // His own page, said plainly: the small "›" on the name was easy to miss (the owner, 2026-11-23).
    link ? h("a", { class: "kt-btn kt-btn--wide", href: `#kid/${p.id}` }, `${p.name}'s history, week and limits →`) : null);
}

async function viewKids() {
  const kids = await api("/kids");
  const cards = h("div", { class: "kids-grid" });
  const redraw = () => api("/kids").then((fresh) => fill(cards, fresh.map((k) => kidCard(k, redraw)))).catch(() => {});
  fill(cards, kids.length ? kids.map((k) => kidCard(k, redraw)) : h("div", { class: "empty-state" }, h("h2", { class: "h-display" }, "No profiles yet"), h("a", { class: "kt-btn kt-btn--primary", href: "#profiles" }, "Add the boys")));
  screen("Kids", {}, cards,
    h("p", { class: "kt-muted", style: "margin:0" }, "Time only counts while a video plays. A video that fits when it starts may finish."));
  timer = setInterval(() => { if (location.hash === "#kids" && kids.length) redraw(); }, 15000);
}

async function viewKid(id) {
  const [kids, limits, report, hist] = await Promise.all([api("/kids"), api(`/limits/${id}`).catch(() => ({})),
    api(`/reports?profile_id=${id}`).catch(() => ({ days: [], channels: [], again: [] })), api(`/history?profile_id=${id}`).catch(() => ({ plays: [], more: false, total: 0 }))]);
  const k = kids.find((x) => x.profile.id === +id);
  if (!k) return go("kids");
  const p = k.profile;
  const holder = h("div");
  const redraw = () => api("/kids").then((fresh) => { const f = fresh.find((x) => x.profile.id === +id); if (f) fill(holder, kidCard(f, redraw, { link: false })); }).catch(() => {});
  fill(holder, kidCard(k, redraw, { link: false }));
  const lim = [limits.weekday_min != null ? `${limits.weekday_min} min weekdays` : null, limits.weekend_min != null ? `${limits.weekend_min} min weekends` : null].filter(Boolean).join(", ") || "No daily limit";
  const histBox = h("div", { class: "kt-stack", style: "gap:12px" });
  let plays = hist.plays, more = hist.more;
  const drawHistory = () => fill(histBox, historyList(plays),
    more ? h("button", { class: "kt-btn", type: "button", style: "align-self:center", onclick: (e) => run(async () => {
      busy(e.currentTarget);
      const r = await api(`/history?profile_id=${id}&before=${plays[plays.length - 1].id}`);
      plays = plays.concat(r.plays);
      more = r.more;
      drawHistory();
    }) }, "Show older") : null);
  drawHistory();
  const clear = h("button", { class: "kt-btn kt-btn--danger", type: "button", style: "align-self:flex-start", onclick: () => {
    if (!clear.dataset.sure) { clear.dataset.sure = "1"; clear.textContent = `Tap again to clear ${p.name}'s history`; return; }
    run(async () => {
      busy(clear);
      await api(`/history?profile_id=${id}`, { method: "DELETE" });
      toast(`${p.name}'s history is cleared`);
      viewKid(id);
    });
  } }, `Clear ${p.name}'s history`);
  screen(p.name, { back: "kids", narrow: true },
    holder,
    h("div", { class: "kt-list" },
      linkRow("Limits and rules", lim, `limits/${id}`),
      linkRow("Picture and name", null, `profile/${id}`)),
    h("h2", { class: "kt-label" }, "This week"), weekBlock(report),
    h("h2", { class: "kt-label" }, hist.total ? `History · ${hist.total} play${hist.total === 1 ? "" : "s"}` : "History"), histBox,
    hist.total ? [clear, h("p", { class: "kt-muted", style: "margin:0" },
      "Clearing removes his plays and which videos he has finished, and the AI's picture of what he likes. His minutes for each day stay, so today's limit still counts.")] : null,
    h("p", { class: "kt-muted", style: "margin:0" }, "Watch history stays on your server. With AI on, video titles from it go to OpenRouter to make suggestions, never his name."));
  timer = setInterval(() => { if (location.hash === `#kid/${id}`) redraw(); }, 15000);
}

// His week: minutes per day, most-watched channels, videos on repeat (was its own screen; on his page since 2026-11-23).
function weekBlock(r) {
  const total = r.days.reduce((a, d) => a + d.seconds, 0);
  const max = Math.max(60, ...r.days.map((d) => d.seconds));
  return [
    h("div", { class: "panel" },
      h("div", { class: "kt-row", style: "justify-content:space-between" }, h("strong", { style: "font-size:22px" }, minutesText(total)), h("span", { class: "kt-muted" }, `${minutesText(total / 7)} a day`)),
      h("div", { class: "bars" }, r.days.map((d) => h("div", { style: `height:${Math.round((d.seconds / max) * 100)}%`, title: `${d.day}: ${minutesText(d.seconds)}` }))),
      h("div", { class: "bar-labels kt-muted" }, r.days.map((d) => h("span", {}, new Date(d.day + "T12:00").toLocaleDateString(undefined, { weekday: "narrow" }))))),
    r.channels.length ? [h("h3", { class: "kt-label" }, "Most watched"), r.channels.map((c) => h("a", { class: "kt-channel linkish", href: `#channel/${c.id}` }, avatar(c.thumb_url, c.title, "kt-avatar--plain"),
      h("div", { class: "kt-video__body" }, h("div", { class: "kt-video__title" }, c.title), h("div", { class: "kt-muted" }, `${c.plays} plays`))))] : null,
    r.again.length ? [h("h3", { class: "kt-label" }, "Watched again and again"), h("div", { class: "kt-list" }, r.again.map((v) =>
      playRow({ item_id: v.id, title: v.title, has_thumb: v.has_thumb, thumb_url: v.thumb_url, duration_s: v.duration_s, channel: v.channel, tv: v.tv, finished: v.finished },
        [`${v.plays} times`, `last ${dayLabel(v.last_ts).toLowerCase()} ${clockTime(v.last_ts)}`])))] : null];
}

const clockTime = (ts) => new Date(ts * 1000).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
function dayLabel(ts) {
  const d = new Date(ts * 1000), today = new Date();
  const yest = new Date(today); yest.setDate(today.getDate() - 1);
  if (d.toDateString() === today.toDateString()) return "Today";
  if (d.toDateString() === yest.toDateString()) return "Yesterday";
  return d.toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" });
}

// One play (or one video on repeat): picture, title, a line of when / channel / TV, and "Watched to the end".
function playRow(pl, lead) {
  const pic = thumb(pl.title ? itemThumb({ id: pl.item_id, has_thumb: pl.has_thumb, thumb_url: pl.thumb_url }) : "", { time: pl.duration_s, style: "width:72px; flex:none" });
  return h(pl.title ? "a" : "div", { class: "kt-list__row dl-queue" + (pl.title ? " linkish" : ""), href: pl.title ? `#video/${pl.item_id}` : null }, pic,
    h("span", { class: "kt-list__text" }, pl.title || "A video no longer in the library",
      h("span", { class: "kt-muted" }, [...lead, pl.channel, pl.tv].filter(Boolean).join(" · ")),
      pl.finished ? h("span", { class: "kt-tag kt-tag--ok", style: "align-self:flex-start; margin-top:4px" }, "Watched to the end") : null));
}

// His plays, newest first, under a heading per day.
function historyList(plays) {
  if (!plays.length) return h("div", { class: "kt-muted" }, "Nothing watched yet. Plays show up here once he watches on a TV.");
  const out = [];
  let day = null, list = null;
  for (const pl of plays) {
    const d = dayLabel(pl.ts);
    if (d !== day) { day = d; list = h("div", { class: "kt-list" }); out.push(h("h3", { class: "kt-label" }, d), list); }
    list.append(playRow(pl, [clockTime(pl.ts)]));
  }
  return out;
}

async function viewLimits(pid) {
  const l = await api(`/limits/${pid}`);
  const p = profiles.find((x) => x.id === +pid) || { name: "" };
  const num = (id, v, ph) => h("input", { id, class: "kt-input num", type: "number", min: 0, value: v ?? "", placeholder: ph || "none" });
  const time = (id, v) => h("input", { id, class: "kt-input", type: "time", value: v || "" });
  const f = {
    weekday_min: num("weekday", l.weekday_min), weekend_min: num("weekend", l.weekend_min), session_min: num("session", l.session_min),
    break_min: num("break", l.break_min, "60"), closed_from: time("cfrom", l.closed_from), closed_to: time("cto", l.closed_to),
    grace_min: num("grace", l.grace_min, "2"), autoplay_n: num("autoplay", l.autoplay_n, "2"),
  };
  let timefit = !!l.timefit, show_timer = !!l.show_timer;
  const val = (x) => (x.value === "" ? null : +x.value);
  screen(`${p.name}'s limits`, { back: `kid/${pid}` },
    h("h2", { class: "kt-label" }, "Time a day"),
    h("div", { class: "kt-list" },
      row(h("label", { for: "weekday" }, "Weekdays, minutes"), f.weekday_min),
      row(h("label", { for: "weekend" }, "Weekends, minutes"), f.weekend_min, "Empty means no daily limit")),
    h("h2", { class: "kt-label" }, "One sitting"),
    h("div", { class: "kt-list" },
      row(h("label", { for: "session" }, "Longest sitting, minutes"), f.session_min),
      row(h("label", { for: "break" }, "Then a break of, minutes"), f.break_min)),
    h("h2", { class: "kt-label" }, "Closed hours"),
    h("div", { class: "kt-list" },
      row(h("label", { for: "cfrom" }, "Closed from"), f.closed_from),
      row(h("label", { for: "cto" }, "Until"), f.closed_to, "Leave both empty to never close")),
    h("h2", { class: "kt-label" }, "When time runs low"),
    h("div", { class: "kt-list" },
      row("Only show videos that finish in time", switchBtn(timefit, "Only show videos that finish in time", (v) => (timefit = v)), "The choice shrinks as time runs down"),
      row(h("label", { for: "grace" }, "May run over by, minutes"), f.grace_min),
      row("Timer on the TV", switchBtn(show_timer, "Timer on the TV", (v) => (show_timer = v))),
      row(h("label", { for: "autoplay" }, "Autoplay, then stop after"), f.autoplay_n, "Videos in a row")),
    h("button", { class: "kt-btn kt-btn--primary kt-btn--wide", type: "button", onclick: () => run(async () => {
      await api(`/limits/${pid}`, { method: "PUT", body: {
        weekday_min: val(f.weekday_min), weekend_min: val(f.weekend_min), session_min: val(f.session_min),
        break_min: val(f.break_min) ?? 60, closed_from: f.closed_from.value || null, closed_to: f.closed_to.value || null,
        timefit, grace_min: val(f.grace_min) ?? 2, show_timer, autoplay_n: val(f.autoplay_n) ?? 2,
      } });
      toast("Saved");
      go(`kid/${pid}`);
    }) }, "Save"));
}

// ---- More ---------------------------------------------------------------------------------------------------------

function themeButton() {
  const b = h("button", { class: "kt-iconbtn", type: "button", "aria-label": "Switch light or dark", title: "Switch light or dark" });
  const draw = () => fill(b, h("svg", { viewBox: "0 0 24 24", "aria-hidden": "true" }, h("path", { d: isDark()
    ? "M12 4v2M12 18v2M4 12h2M18 12h2M6.3 6.3l1.4 1.4M16.3 16.3l1.4 1.4M6.3 17.7l1.4-1.4M16.3 7.7l1.4-1.4M12 8.5a3.5 3.5 0 1 0 0 7a3.5 3.5 0 1 0 0-7z"
    : "M19 14.5A7.5 7.5 0 0 1 9.5 5a7.5 7.5 0 1 0 9.5 9.5z" })));
  b.addEventListener("click", () => { setTheme(isDark() ? "light" : "dark"); draw(); });
  draw();
  return b;
}

async function viewSettingsMenu() {
  const [auto, devices, plex, ai, st] = await Promise.all([api("/automation").catch(() => ({})), api("/devices").catch(() => []),
    api("/plex").catch(() => ({ connected: false })), api("/ai").catch(() => ({})), api("/settings").catch(() => ({}))]);
  const nWords = (st.blocked_words || []).length, nSkips = (st.skip_categories || []).length;
  const theme = { system: "Same as this device", light: "Light", dark: "Dark" }[getTheme()];
  const group = (title, ...rows) => h("section", { class: "settings-group" }, h("h2", { class: "kt-label" }, title), h("div", { class: "kt-list" }, rows));
  const sub = (title, text, right, hash) => h("a", { class: "kt-list__row", href: "#" + hash }, h("span", { class: "kt-list__text" }, title, text ? h("span", { class: "kt-muted" }, text) : null), right);
  const val = (t) => h("span", { class: "kt-list__value" }, t);
  screen("Settings", { action: themeButton() },
    h("div", { class: "settings-groups" },
      group("Household",
        row("Vacation mode", switchBtn(!!auto.vacation_mode, "Vacation mode", (v) => run(async () => {
          await api("/automation/vacation", { method: "POST", body: { on: v } });
          toast(v ? "Vacation mode on: weekend time every day" : "Vacation mode off");
        })), "Weekend time every day"),
        sub("TVs", "Pair a TV, remove one", val(`${devices.filter((d) => !d.revoked).length} paired`), "tvs"),
        sub("Profiles", "Add or remove a boy, a guest or a grown-up", val(`${profiles.length}`), "profiles")),
      group("Safety",
        sub("Blocked words and parts to skip", "Words that always wait for you; sponsor reads, intros to skip",
          val(`${nWords} word${nWords === 1 ? "" : "s"} · ${nSkips} skipped`), "safety")),
      group("Connections",
        sub("Plex", null, val(plex.connected ? `Connected to ${plex.name}` : "Not connected"), "plex-connect"),
        sub("AI", "Ideas for you, a “Picked for you” row for the boys", val(ai.enabled ? "On" : "Off"), "ai"),
        sub("Home Assistant", "Buttons and sensors for the house", val("›"), "home-assistant")),
      group("This page",
        sub("Appearance", null, val(theme), "appearance"),
        sub("Change password", null, val("›"), "password"))),
    h("button", { class: "kt-btn kt-btn--quiet", type: "button", style: "align-self:flex-start", onclick: () => run(async () => {
      await api("/auth/logout", { method: "POST" });
      signIn();
    }) }, "Sign out"));
}

// How much room videos may take (was Settings › Library size): lives at the foot of Downloads (nav audit N5).
async function drawLibrarySize(box) {
  const st = await api("/settings");
  const cap = h("input", { id: "cap", class: "kt-input num", type: "number", min: 1, value: st.storage_cap_gb });
  const pct = Math.min(100, (st.library_gb / st.storage_cap_gb) * 100);
  fill(box,
    h("div", { class: "panel" },
      h("div", { class: "kt-row", style: "justify-content:space-between" }, h("strong", {}, `${st.library_gb} GB of ${st.storage_cap_gb} GB`), h("span", { class: "kt-muted" }, `${st.library_videos} videos`)),
      h("div", { class: "kt-bar kt-bar--time" + (pct > 90 ? " kt-bar--low" : "") }, h("i", { style: `width:${pct}%` })),
      st.disk ? h("div", { class: "kt-muted" }, `${st.disk.free_gb} GB free on the server's disk`) : null),
    h("form", { class: "kt-list", onsubmit: (e) => { e.preventDefault(); run(async () => {
      const btn = e.currentTarget.querySelector("button");
      busy(btn);
      try { await api("/settings", { method: "PUT", body: { storage_cap_gb: +cap.value || 500 } }); } finally { busy(btn, false); }
      toast(`Most room for videos: ${+cap.value || 500} GB`);
      kickActivity();
      await drawLibrarySize(box);
    }); } }, row(h("label", { for: "cap" }, "Most room for videos, GB"), h("span", { class: "kt-row", style: "gap:8px; flex-wrap:nowrap" }, cap, h("button", { class: "kt-btn kt-btn--quiet" }, "Save")))),
    h("p", { class: "kt-muted", style: "margin:0" }, "When the library reaches this size, downloads pause until you raise it or delete videos. Channel keeping rules (on each subscription) free up room."));
}

function viewAppearance() {
  const choices = [["system", "Same as this device"], ["light", "Light"], ["dark", "Dark"]];
  const list = h("div", { class: "kt-list" });
  const draw = () => fill(list, choices.map(([v, label]) => h("button", { class: "kt-list__row", type: "button", style: "width:100%; background:none; border:0; font:inherit; color:inherit; text-align:left; cursor:pointer",
    "aria-pressed": getTheme() === v ? "true" : "false", onclick: () => { setTheme(v); draw(); } },
    h("span", { class: "kt-list__text" }, label), getTheme() === v ? icon("check") : null)));
  draw();
  screen("Appearance", { back: "settings" }, list,
    h("p", { class: "kt-muted", style: "margin:0" }, "Kept on this device only, so a phone and a computer can differ."));
}

// ---- shared by Downloads, Jobs and the activity pill ---------------------------------------------------------------

const when = (t) => {
  if (!t) return "";
  const d = t - Date.now() / 1000, a = Math.abs(d);
  const txt = a < 90 ? "a minute" : a < 3600 ? `${Math.round(a / 60)} min` : a < 86400 ? `${Math.round(a / 3600)} h` : `${Math.round(a / 86400)} days`;
  return d > 0 ? (a < 60 ? "any moment" : `in ${txt}`) : a < 60 ? "just now" : `${txt} ago`;
};
const clock = (s) => {
  s = Math.max(0, Math.round(s || 0));
  const hh = Math.floor(s / 3600), mm = Math.floor((s % 3600) / 60), ss = s % 60;
  return hh ? `${hh}:${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}` : `${mm}:${String(ss).padStart(2, "0")}`;
};
const took = (s) => (s < 60 ? `${Math.max(1, Math.round(s))}s` : s < 3600 ? `${Math.floor(s / 60)}m ${Math.round(s % 60)}s` : `${Math.floor(s / 3600)}h ${Math.round((s % 3600) / 60)}m`);
const bytesText = (n) => (!n ? "" : n >= 1e9 ? `${(n / 1e9).toFixed(n >= 1e10 ? 0 : 1)} GB` : `${(n / 1e6).toFixed(n >= 1e8 ? 0 : 1)} MB`);
// "42% · 120.3 MB / 286 MB · 4.2 MB/s · ETA 0:39"
const progressLine = (d) => [`${Math.round(d.percent)}%`, d.total ? `${bytesText(d.downloaded)} / ${bytesText(d.total)}` : null,
  d.speed ? `${bytesText(d.speed)}/s` : null, d.eta != null ? `ETA ${clock(d.eta)}` : null].filter(Boolean).join(" · ");

// Update a list in place, by key, so buttons and bars are not replaced under a finger every few seconds.
function sync(container, items, keyOf, create, update) {
  const have = new Map([...container.children].filter((el) => el.dataset.key).map((el) => [el.dataset.key, el]));
  const kept = new Set();
  let prev = null;
  for (const it of items) {
    const k = String(keyOf(it));
    let el = have.get(k);
    if (!el) { el = create(it); el.dataset.key = k; }
    kept.add(el);
    update(el, it);
    const want = prev ? prev.nextSibling : container.firstChild;
    if (el !== want) container.insertBefore(el, want);
    prev = el;
  }
  for (const el of [...container.children]) if (!kept.has(el)) el.remove();
}
// Only redraw a block when what it shows has changed.
function fillIfChanged(el, sig, build) {
  if (el.dataset.sig === sig) return;
  el.dataset.sig = sig;
  fill(el, build());
}

// ---- Downloads: live progress, what's waiting, history (ADR 0032, revised; after an earlier download manager) ----------------------

const dlState = { status: "all", q: "", page: 1 };

async function viewDownloads(toSize = false) {
  const head = h("div", { class: "kt-row" });
  const banners = h("div", { class: "kt-stack", style: "gap:8px" });
  const activeBox = h("div", { class: "kt-stack", style: "gap:12px" });
  const activeEmpty = h("div", { class: "kt-muted" });
  const queueWrap = h("div", { class: "kt-stack", style: "gap:8px" });
  const histBox = h("div", { class: "kt-stack", style: "gap:0" }, skelRows(3));
  const pager = h("div", { class: "kt-row", style: "justify-content:space-between" });
  const storage = h("div", { class: "kt-stack", style: "gap:8px" }, skelRows(1));
  const sizeHead = h("h2", { class: "kt-label", id: "library-size" }, "Library size");
  const toSizeBox = () => sizeHead.scrollIntoView({ behavior: "smooth", block: "start" });
  const seg = h("div", { class: "seg", role: "group", "aria-label": "Show" });
  const search = h("input", { class: "kt-input kt-input--search", type: "search", value: dlState.q, placeholder: "Search downloads", "aria-label": "Search downloads" });
  let counts = null, lastCounts = "";

  const act = (path, msg) => run(async () => { await api(path, { method: "POST" }); if (msg) toast(msg); kickActivity(); await tick(); loadHistory(); });

  const card = (d) => {
    const stop = h("button", { class: "kt-btn dl-stop", type: "button", onclick: () => { busy(stop); stop.textContent = "Stopping…"; act(`/downloads/${d.job_id}/stop`); } }, "Stop");
    return h("div", { class: "dl-card" },
      h("a", { class: "dl-card__thumb", href: `#video/${d.item_id}`, "aria-label": d.title }, thumb(d.thumb)),
      h("div", { class: "dl-card__body" },
        h("a", { class: "kt-video__title linkish", href: `#video/${d.item_id}` }, d.title),
        h("div", { class: "kt-muted" }, d.channel),
        h("div", { class: "kt-bar dl-bar", role: "progressbar", "aria-label": "Download", "aria-valuemin": 0, "aria-valuemax": 100 }, h("i")),
        h("div", { class: "dl-line" }),
        h("span", { class: "kt-tag dl-phase" })),
      stop);
  };
  const updateCard = (el, d) => {
    const has = d.percent != null;
    const bar = el.querySelector(".dl-bar"), line = el.querySelector(".dl-line"), phase = el.querySelector(".dl-phase"), stop = el.querySelector(".dl-stop");
    bar.hidden = !has;
    line.hidden = !has;
    phase.hidden = has;
    if (has) {
      bar.setAttribute("aria-valuenow", Math.round(d.percent));
      bar.firstChild.style.width = `${d.percent}%`;
      line.textContent = progressLine(d) + (d.phase && d.phase !== "Downloading" ? ` · ${d.phase.toLowerCase()}` : "");
    } else phase.textContent = d.stopping ? "Stopping…" : d.phase;
    if (d.stopping && !stop.hasAttribute("aria-busy")) { busy(stop); stop.textContent = "Stopping…"; }
  };

  const drawActive = (a) => {
    counts = a.counts;
    // Keep the pill in step with this page instead of waiting for its own slower poll.
    if (lastActivity && (lastActivity.downloads.length !== a.active.length || lastActivity.queued !== counts.waiting)) kickActivity();
    fillIfChanged(head, `${a.paused}|${counts.failed}`, () => [
      h("button", { class: "kt-btn" + (a.paused ? " kt-btn--primary" : ""), type: "button", onclick: (e) => run(async () => {
        busy(e.currentTarget);
        await api("/settings", { method: "PUT", body: { downloads_paused: !a.paused } });
        toast(a.paused ? "Downloads resumed" : "Paused. The one in progress finishes.");
        kickActivity();
        await tick();
      }) }, a.paused ? "Resume downloads" : "Pause downloads"),
      counts.failed ? h("button", { class: "kt-btn", type: "button", onclick: (e) => {
        const b = e.currentTarget;
        if (!b.dataset.sure) { b.dataset.sure = "1"; b.textContent = `Tap again to retry ${counts.failed}`; return; }
        act("/downloads/retry-failed", `Trying ${counts.failed} again`);
      } }, `Retry all failed (${counts.failed})`) : null]);
    fillIfChanged(banners, `${a.paused}|${a.storage_full}|${counts.waiting}`, () => [
      a.paused ? h("div", { class: "kt-banner kt-banner--warn" }, h("span", {}, h("strong", {}, "Downloads are paused. "), counts.waiting ? `${counts.waiting} waiting.` : "Nothing is waiting.")) : null,
      a.storage_full ? h("div", { class: "kt-banner kt-banner--bad" }, h("span", {}, h("strong", {}, "The library is full. "), "Downloads wait until you raise the size limit or delete videos. ",
        h("a", { href: "#downloads", onclick: (e) => { e.preventDefault(); toSizeBox(); } }, "Library size ↓"))) : null]);
    sync(activeBox, a.active, (d) => d.job_id, card, updateCard);
    activeEmpty.hidden = a.active.length > 0;
    const ready = a.queued.some((q) => !q.retry_at || q.retry_at * 1000 <= Date.now());
    activeEmpty.textContent = a.paused ? "Nothing downloading while paused." : ready ? "Starting the next one…" : "Nothing downloading.";
    fillIfChanged(queueWrap, a.queued.map((q) => `${q.job_id}:${q.retry_at ? when(q.retry_at) : ""}`).join(",") + "|" + counts.waiting, () => (a.queued.length ? [
      h("h2", { class: "kt-label" }, `Up next (${counts.waiting})`),
      h("div", { class: "kt-list" }, a.queued.slice(0, 10).map((q) => h("div", { class: "kt-list__row dl-queue" },
        thumb(q.thumb, { style: "width:72px; flex:none" }),
        h("span", { class: "kt-list__text" }, q.title, h("span", { class: "kt-muted" }, q.channel),
          q.retry_at ? h("span", { class: "kt-muted dl-retry", title: q.error }, `YouTube refused it (try ${q.attempts}). Trying again ${q.retry_at * 1000 > Date.now() ? when(q.retry_at) : "next"}.`) : null),
        iconBtn("x", "Take out of the queue", () => act(`/downloads/${q.job_id}/stop`, "Taken out of the queue"))))),
      counts.waiting > 10 ? h("div", { class: "kt-muted" }, `and ${counts.waiting - 10} more`) : null] : []));
    const sig = `${counts.done}|${counts.failed}|${counts.stopped}`;
    if (lastCounts && sig !== lastCounts) loadHistory();
    lastCounts = sig;
  };

  const drawSeg = () => fill(seg, [["all", "All"], ["done", "Done"], ["failed", "Failed"], ["stopped", "Stopped"]].map(([v, label]) =>
    h("button", { type: "button", "aria-pressed": dlState.status === v ? "true" : "false", onclick: () => { dlState.status = v; dlState.page = 1; drawSeg(); loadHistory(); } },
      label + (counts && v !== "all" && counts[v] ? ` ${counts[v]}` : ""))));

  const histRow = (r) => {
    const tag = r.status === "done" ? h("span", { class: "kt-tag kt-tag--ok" }, "Done") : r.status === "failed" ? h("span", { class: "kt-tag kt-tag--bad" }, "Failed") : h("span", { class: "kt-tag" }, "Stopped");
    const meta = [r.channel, r.finished_at ? when(r.finished_at) : null, bytesText(r.bytes),
      r.status === "done" && r.started_at && r.finished_at ? `took ${took(r.finished_at - r.started_at)}` : null].filter(Boolean).join(" · ");
    return h("div", { class: "dl-hist" },
      h("a", { href: `#video/${r.item_id}`, "aria-label": r.title }, thumb(r.thumb, { time: r.duration_s, style: "width:104px" })),
      h("div", { class: "dl-card__body" },
        h("a", { class: "kt-video__title linkish", href: `#video/${r.item_id}` }, r.title),
        h("div", { class: "kt-muted dl-meta" }, meta),
        h("div", { class: "kt-muted dl-cell" }, r.channel),
        h("div", { class: "kt-row", style: "gap:6px" }, tag, r.status === "done" && r.approval === "waiting" ? h("span", { class: "kt-tag kt-tag--warn" }, "Waiting in Approve") : null),
        r.status === "failed" && r.error ? h("div", { class: "err dl-error", title: r.error }, r.error.replace(/^ERROR:\s*/, "").slice(0, 180)) : null),
      h("span", { class: "kt-muted dl-cell" }, bytesText(r.bytes)),
      h("span", { class: "kt-muted dl-cell" }, r.status === "done" && r.started_at && r.finished_at ? took(r.finished_at - r.started_at) : ""),
      h("span", { class: "kt-muted dl-cell" }, r.finished_at ? when(r.finished_at) : ""),
      h("span", { class: "dl-act" }, r.status !== "done" ? iconBtn("retry", "Try again", () => act(`/downloads/${r.job_id}/retry`, "Back in the queue")) : null));
  };
  const loadHistory = () => run(async () => {
    const p = new URLSearchParams({ status: dlState.status, q: dlState.q, page: dlState.page });
    const hst = await api("/downloads/history?" + p);
    if (hst.page > hst.pages) { dlState.page = hst.pages; return loadHistory(); }
    drawSeg();
    fill(histBox, hst.rows.length ? [h("div", { class: "dl-hist dl-hist--head kt-muted" }, h("span", {}), h("span", {}, "Video"), h("span", {}, "Size"), h("span", {}, "Took"), h("span", {}, "When"), h("span", {})), hst.rows.map(histRow)] : h("div", { class: "empty" }, dlState.q || dlState.status !== "all" ? "Nothing matches." : "No downloads yet. Search in the Library to add videos or subscribe to a channel."));
    fill(pager, hst.pages > 1 ? [
      h("button", { class: "kt-btn kt-btn--quiet", type: "button", disabled: hst.page <= 1, onclick: () => { dlState.page--; loadHistory(); } }, "Newer"),
      h("span", { class: "kt-muted" }, `Page ${hst.page} of ${hst.pages} · ${hst.total} downloads`),
      h("button", { class: "kt-btn kt-btn--quiet", type: "button", disabled: hst.page >= hst.pages, onclick: () => { dlState.page++; loadHistory(); } }, "Older")] : []);
  });
  let typing = null;
  search.addEventListener("input", () => { clearTimeout(typing); typing = setTimeout(() => { dlState.q = search.value.trim(); dlState.page = 1; loadHistory(); }, 300); });

  let inflight = false;
  const tick = async () => {
    if (inflight) return;
    inflight = true;
    try { drawActive(await api("/downloads/active")); } finally { inflight = false; }
  };

  screen("Downloads", {},
    head, banners,
    h("h2", { class: "kt-label" }, "Downloading now"), activeBox, activeEmpty,
    queueWrap,
    h("h2", { class: "kt-label" }, "History"), seg, search, histBox, pager,
    sizeHead, storage);
  drawSeg();
  await tick();
  loadHistory();
  const sized = drawLibrarySize(storage).catch(() => fill(storage));
  if (toSize) sized.then(toSizeBox);
  timer = setInterval(() => { if (location.hash === "#downloads") tick().catch(() => {}); }, 2000);
}

// ---- Jobs: what the server does on its own schedule (ADR 0032) ---------------------------------------------------

async function viewJobs() {
  const list = h("div", { class: "kt-stack", style: "gap:12px" });
  const notes = h("div", { class: "kt-stack", style: "gap:8px" });
  const units = [["min", 60], ["hours", 3600], ["days", 86400]];
  const split = (s) => (s % 86400 === 0 ? [s / 86400, 86400] : s % 3600 === 0 ? [s / 3600, 3600] : [Math.round(s / 60), 60]);

  const card = (j) => {
    const btn = h("button", { class: "kt-btn job-go", type: "button" });
    const el = h("div", { class: "job-card" },
      h("div", { class: "job-card__head" },
        h("div", {}, h("div", { class: "job-card__title" }, j.label), h("div", { class: "kt-muted" }, j.about)), btn),
      h("div", { class: "kt-row job-status", style: "gap:8px" }),
      h("div", { class: "err job-error", style: "font-size:14px" }));
    btn.addEventListener("click", () => run(async () => {
      const now = el._job;
      busy(btn);
      try {
        await api(`/background-jobs/${now.name}/${now.running ? "stop" : "run"}`, { method: "POST" });
        kickActivity();
        await tick();
      } finally { busy(btn, false); }
    }));
    if (j.every_s) {
      const [n, unit] = split(j.every_s);
      const num = h("input", { class: "kt-input num", type: "number", min: 1, value: n, "aria-label": `${j.label}: how often` });
      const sel = h("select", { class: "kt-input", "aria-label": "Unit" }, units.map(([name, secs]) => h("option", { value: secs, selected: secs === unit }, name)));
      el.append(h("form", { class: "kt-row job-sched", onsubmit: (e) => { e.preventDefault(); run(async () => {
        const minutes = Math.round(((+num.value || 0) * +sel.value) / 60);
        if (minutes < 5) throw new Error("Five minutes is the shortest.");
        await api(`/background-jobs/${j.name}/schedule`, { method: "PUT", body: { minutes } });
        toast(`${j.label}: every ${num.value} ${sel.selectedOptions[0].textContent}`);
        await tick();
      }); } }, h("span", { class: "kt-muted" }, "Every"), num, sel, h("button", { class: "kt-btn kt-btn--quiet" }, "Save"), h("span", { class: "kt-muted job-next" })));
    }
    return el;
  };
  const update = (el, j) => {
    el._job = j;
    const btn = el.querySelector(".job-go"), last = j.last;
    btn.textContent = j.running ? "Stop" : "Run now";
    btn.hidden = j.running && !j.stoppable;
    btn.disabled = !j.running && !j.enabled;
    const badge = j.running ? h("span", { class: "kt-tag kt-tag--busy" }, h("span", { class: "kt-spinner" }), "Running")
      : !j.enabled ? h("span", { class: "kt-tag" }, "Off")
      : last && last.state === "failed" ? h("span", { class: "kt-tag kt-tag--bad" }, "Error") : h("span", { class: "kt-tag" }, "Idle");
    const text = j.running ? (j.note || "Working…")
      : !j.enabled ? j.disabled_note
      : last ? [`Last run ${when(last.finished_at || last.started_at)}`, last.finished_at ? `took ${took(last.finished_at - last.started_at)}` : null, last.state === "stopped" ? "stopped" : last.result].filter(Boolean).join(" · ")
      : "Not run yet";
    fillIfChanged(el.querySelector(".job-status"), `${j.running}|${j.enabled}|${last && last.id}|${text}`, () => [badge, h("span", { class: "kt-muted" }, text)]);
    const err = el.querySelector(".job-error");
    err.hidden = !(last && last.state === "failed" && last.error && !j.running);
    err.textContent = last && last.error ? last.error.slice(0, 120) : "";
    const next = el.querySelector(".job-next");
    if (next) next.textContent = j.running ? "" : j.next_at ? `· next ${when(j.next_at)}` : "· paused";
  };

  let first = true;
  const pauseRow = h("div", { class: "kt-list" });
  const tick = async () => {
    const bg = await api("/background-jobs");
    const yt = bg.ytdlp || {};
    if (first) {
      first = false;
      fill(pauseRow, row("Pause scheduled jobs", switchBtn(bg.checks_paused, "Pause scheduled jobs", (v) => run(async () => {
        await api("/background-jobs/pause", { method: "PUT", body: { checks_paused: v } });
        kickActivity();
        await tick();
      })), "Run now still works while paused"));
    }
    fillIfChanged(notes, `${bg.checks_paused}|${yt.have}|${yt.newest}`, () => [
      bg.checks_paused ? h("div", { class: "kt-banner kt-banner--warn" }, h("span", {}, "Scheduled jobs are paused.")) : null,
      yt.have && yt.newest && yt.have !== yt.newest ? h("div", { class: "kt-banner kt-banner--warn" }, h("span", {}, h("strong", {}, `yt-dlp ${yt.newest} is out. `), `This server has ${yt.have}. Rebuild the image to update (bash scripts/deploy.sh).`)) : null]);
    drawLive(bg);
    // Leave the cards alone while a schedule box is being typed in. Only a box or a dropdown counts: a pressed
    // Run now / Save button keeps focus too, and treating that as typing froze the page after any click.
    if (!list.querySelector("input:focus, select:focus") || !list.children.length) sync(list, bg.jobs, (j) => j.name, card, update);
  };

  // Running now: every job at work, imports included (they have no card). Up next: the schedule, soonest first.
  // Jobs never wait in a line: a job runs, or waits for its time.
  const runBox = h("div", { class: "kt-list" }), runEmpty = h("div", { class: "kt-muted" }, "Nothing running.");
  const nextBox = h("div", { class: "kt-list" });
  const liveRow = (r) => h("div", { class: "kt-list__row" }, h("span", { class: "kt-spinner" }),
    h("span", { class: "kt-list__text" }, h("span", { class: "live-label" }), h("span", { class: "kt-muted live-note" })),
    h("button", { class: "kt-btn kt-btn--quiet live-stop", type: "button", onclick: (e) => run(async () => {
      busy(e.currentTarget);
      e.currentTarget.textContent = "Stopping…";
      await api(`/background-jobs/${r.name}/stop`, { method: "POST" });
      kickActivity();
    }) }, "Stop"));
  const liveUpdate = (el, r, now) => {
    el.querySelector(".live-label").textContent = r.label;
    el.querySelector(".live-note").textContent = [r.note, `for ${took(now - r.started_at)}`].filter(Boolean).join(" · ");
    el.querySelector(".live-stop").hidden = !r.stoppable;
  };
  const drawLive = (bg) => {
    sync(runBox, bg.running, (r) => r.name, liveRow, (el, r) => liveUpdate(el, r, bg.now));
    runBox.hidden = !bg.running.length;
    runEmpty.hidden = bg.running.length > 0;
    const every = (s) => (s % 86400 === 0 ? `every ${s / 86400 === 1 ? "day" : `${s / 86400} days`}` : s % 3600 === 0 ? `every ${s / 3600 === 1 ? "hour" : `${s / 3600} hours`}` : `every ${Math.round(s / 60)} min`);
    const next = bg.jobs.filter((j) => j.next_at && !j.running).sort((a, b) => a.next_at - b.next_at).slice(0, 5);
    const rows = next.map((j) => [j.label, when(j.next_at), j.every_s ? every(j.every_s) : ""]);
    fillIfChanged(nextBox, `${bg.checks_paused}|${JSON.stringify(rows)}`, () => bg.checks_paused
      ? row("Paused", null, "Nothing starts on its own until you turn the pause off. Run now still works.")
      : rows.length ? rows.map(([label, at, often]) => row(label, h("span", { class: "kt-list__value" }, at), often))
      : row("Nothing scheduled", null));
  };

  screen("Jobs", {},
    h("p", { class: "kt-muted", style: "margin:0" }, "What the server does on its own. Video downloads have their own page."),
    pauseRow, notes,
    h("h2", { class: "kt-label" }, "Running now"), runBox, runEmpty,
    h("h2", { class: "kt-label" }, "Up next"), nextBox,
    h("h2", { class: "kt-label" }, "All jobs"), list);
  fill(list, skelRows(3));
  await tick().catch((e) => { fill(list); throw e; });
  timer = setInterval(() => { if (location.hash === "#jobs") tick().catch(() => {}); }, 3000);
}

// ---- the activity pill, on every screen (ADR 0032, revised; after an earlier download manager's "scrobbler") -----------------------
// One small pill that is always there: a dot, a label, a count. Tap it for the panel. Both are built once and
// updated in place, so the panel stays open and steady while the numbers change.

const activityEl = document.getElementById("activity");
activityEl.className = "scrob";
let activityTimer = null, lastActivity = null;
const scrob = {
  dot: h("span", { class: "scrob-dot" }), label: h("strong", { class: "scrob-label" }), suffix: h("span", { class: "scrob-suffix" }),
  chips: h("span", { class: "kt-row", style: "gap:4px" }), jobs: h("div", { class: "scrob-sec" }), errors: h("div", { class: "scrob-sec" }),
  dlTitle: h("div", { class: "scrob-title" }), dls: h("div", { class: "scrob-dls" }), dlMore: h("div", { class: "kt-muted scrob-more" }),
  empty: h("div", { class: "kt-muted" }),
};
scrob.panel = h("div", { class: "scrob-panel", role: "dialog", "aria-label": "Background activity", hidden: true },
  h("div", { class: "scrob-head" }, h("strong", {}, "Background activity"), scrob.chips),
  scrob.jobs, scrob.errors, scrob.dlTitle, scrob.dls, scrob.dlMore, scrob.empty,
  h("div", { class: "scrob-foot" }, h("a", { href: "#downloads" }, "Downloads →"), h("a", { href: "#jobs" }, "Jobs →")));
scrob.pill = h("button", { class: "scrob-pill", type: "button", "aria-expanded": "false", onclick: () => setScrob(scrob.panel.hidden) },
  scrob.dot, scrob.label, scrob.suffix,
  h("svg", { viewBox: "0 0 24 24", "aria-hidden": "true", class: "scrob-chev" }, h("path", { d: "M6 15l6-6 6 6" })));
activityEl.append(scrob.panel, scrob.pill);

function setScrob(open) {
  scrob.panel.hidden = !open;
  scrob.pill.setAttribute("aria-expanded", String(open));
  activityEl.classList.toggle("open", open);
  if (open) { drawActivity(); kickActivity(); }
}
document.addEventListener("click", (e) => { if (!scrob.panel.hidden && !activityEl.contains(e.target)) setScrob(false); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") setScrob(false); });
window.addEventListener("hashchange", () => setScrob(false));

function kickActivity() { clearTimeout(activityTimer); pollActivity(); }

async function pollActivity() {
  clearTimeout(activityTimer);
  try { lastActivity = await api("/activity"); } catch { /* keep showing the last answer */ }
  drawActivity();
  const a = lastActivity;
  const busyNow = a && (a.running.length || a.downloads.length || (a.queued && !a.downloads_paused));
  activityTimer = setTimeout(pollActivity, document.hidden ? 30000 : busyNow ? 2500 : !scrob.panel.hidden ? 4000 : 8000);
}

function drawActivity() {
  const a = lastActivity;
  if (!a || nav.hidden) return (activityEl.hidden = true);
  activityEl.hidden = false;
  const dl = a.downloads, known = dl.filter((d) => d.percent != null);
  const avg = known.length ? Math.round(known.reduce((x, d) => x + d.percent, 0) / known.length) : null;
  let state = "idle", label = "All quiet", suffix = "";
  if (dl.length || (a.queued && !a.downloads_paused && !a.storage_full)) {
    state = "run";  // between two downloads there is a short gap with nothing active: still downloading
    label = dl.length > 1 ? `${dl.length} downloading` : "Downloading";
    suffix = [avg != null ? `${avg}%` : dl.length ? dl[0].phase : null, a.queued ? `${a.queued} waiting` : null, a.running.length ? `+${a.running.length} job${a.running.length > 1 ? "s" : ""}` : null].filter(Boolean).join(" · ");
  } else if (a.running.length) {
    state = "run";
    label = a.running[0].label;
    suffix = a.running.length > 1 ? `+${a.running.length - 1}` : "";
  } else if (a.failed || a.errors.length) {
    state = "error";
    label = a.failed ? `${a.failed} download${a.failed > 1 ? "s" : ""} failed` : `${a.errors[0].label}: error`;
    suffix = a.failed && a.errors.length ? `+${a.errors.length}` : !a.failed && a.errors.length > 1 ? `+${a.errors.length - 1}` : "";
  } else if (a.imports && a.imports.length) {
    // An import that is ready to review, stopped, or finished, until the parent opens it.
    const im = a.imports[0];
    state = "news";
    label = im.state === "done" ? "Import finished" : im.stopped ? "Import stopped" : "Import ready to review";
    suffix = im.state === "done" && im.added ? `${im.added} added` : "";
  } else if (a.downloads_paused || a.checks_paused) {
    state = "warn";
    label = a.downloads_paused && a.checks_paused ? "Paused" : a.downloads_paused ? "Downloads paused" : "Jobs paused";
    suffix = a.downloads_paused && a.queued ? `${a.queued} waiting` : "";
  }
  activityEl.dataset.state = state;
  // The nav's Downloads and Jobs places carry a count when something needs a look, like Approve does.
  for (const [id, n] of [["downloads-dot", a.failed], ["jobs-dot", a.errors.length]]) {
    const dot = document.getElementById(id);
    dot.textContent = n || "";
    dot.hidden = !n;
  }
  scrob.dot.className = `scrob-dot scrob-dot--${state}`;
  scrob.label.textContent = label;
  scrob.suffix.textContent = suffix ? `· ${suffix}` : "";
  if (scrob.panel.hidden) return;

  fillIfChanged(scrob.chips, `${a.downloads_paused}|${a.checks_paused}`, () => [
    a.downloads_paused ? h("span", { class: "kt-tag kt-tag--warn" }, "downloads paused") : null,
    a.checks_paused ? h("span", { class: "kt-tag kt-tag--warn" }, "jobs paused") : null]);
  fill(scrob.jobs, a.running.length ? [h("div", { class: "scrob-title" }, "Jobs"), a.running.map((r) => h("div", { class: "scrob-row" },
    h("span", { class: "kt-spinner" }), h("span", { class: "scrob-name" }, r.label, r.note ? h("span", { class: "kt-muted" }, ` ${r.note}`) : null),
    h("span", { class: "kt-muted" }, took(a.now - r.started_at))))] : []);
  const ims = a.imports || [];
  fillIfChanged(scrob.errors, `${a.failed}|${a.errors.map((e) => e.id).join(",")}|${ims.map((i) => `${i.id}${i.state}${i.stopped}`).join(",")}`, () => (a.failed || a.errors.length || ims.length ? [h("div", { class: "scrob-title" }, "Needs a look"),
    ims.map((i) => h("a", { class: "scrob-row", href: `#import/${i.id}` }, h("span", { class: "scrob-dot scrob-dot--news" }),
      h("span", { class: "scrob-name" }, i.state === "done" ? `Import finished${i.added ? `: ${i.added} added` : ""}` : i.stopped ? "Import stopped: the rest wait for you" : "Import ready to review"),
      h("span", {}, "Open →"))),
    a.failed ? h("a", { class: "scrob-row scrob-err", href: "#downloads", onclick: () => { dlState.status = "failed"; dlState.page = 1; } },
      h("span", { class: "scrob-dot scrob-dot--error" }), h("span", { class: "scrob-name" }, `${a.failed} download${a.failed > 1 ? "s" : ""} failed`), h("span", {}, "Open →")) : null,
    a.errors.map((e) => h("a", { class: "scrob-row scrob-err", href: "#jobs", title: e.error },
      h("span", { class: "scrob-dot scrob-dot--error" }), h("span", { class: "scrob-name" }, `${e.label}: ${e.error.slice(0, 44)}`)))] : []));
  scrob.dlTitle.hidden = !dl.length;
  scrob.dlTitle.textContent = `Downloads · ${dl.length} active${a.queued ? ` · ${a.queued} waiting` : ""}`;
  sync(scrob.dls, dl.slice(0, 4), (d) => d.job_id,
    (d) => h("div", { class: "scrob-dl" },
      h("div", { class: "scrob-row" }, h("a", { class: "scrob-name", href: `#video/${d.item_id}` }, d.title), h("span", { class: "kt-muted scrob-num" })),
      h("div", { class: "scrob-bar" }, h("i"))),
    (el, d) => {
      const has = d.percent != null;
      el.querySelector(".scrob-num").textContent = has ? [`${Math.round(d.percent)}%`, d.speed ? `${bytesText(d.speed)}/s` : null].filter(Boolean).join(" · ") : d.phase;
      const bar = el.querySelector(".scrob-bar");
      bar.classList.toggle("scrob-bar--phase", !has);
      bar.firstChild.style.width = has ? `${d.percent}%` : "100%";
    });
  scrob.dlMore.hidden = dl.length <= 4;
  scrob.dlMore.textContent = `+ ${dl.length - 4} more`;
  const quiet = !dl.length && !a.running.length;
  scrob.empty.hidden = !quiet;
  scrob.empty.textContent = quiet ? `Nothing running.${a.queued && a.downloads_paused ? ` ${a.queued} downloads wait while paused.` : ""}${a.next ? ` Next: ${a.next.label} ${when(a.next.at)}.` : ""}` : "";
}
document.addEventListener("visibilitychange", () => { if (!document.hidden && !nav.hidden) kickActivity(); });

// Kept while the page is open, so allowing a title does not lose the section or search you were in.
const plexState = { title: "", items: null, filter: "", pick: null };

const plexPoster = (rk, title, cls = "") => {
  const el = h("div", { class: "poster " + cls });
  if (/^\d+$/.test(String(rk || ""))) {
    const img = h("img", { src: `/api/admin/plex/poster/${rk}`, alt: "", loading: "lazy" });
    img.onerror = () => fill(el, h("span", { class: "poster__letter" }, (title || "?").slice(0, 1)));
    fill(el, img);
  } else fill(el, h("span", { class: "poster__letter" }, (title || "?").slice(0, 1)));
  return el;
};

async function viewPlex() {
  const st = await api("/plex");
  if (!st.connected) {
    return screen("Plex", { back: "add" }, h("div", { class: "empty-state" }, h("h2", { class: "h-display" }, "Plex isn't connected"),
      h("p", { style: "margin:0" }, st.error || "Connect it once, then allow the shows and movies the boys may watch."),
      h("a", { class: "kt-btn kt-btn--primary", href: "#plex-connect" }, "Connect Plex")));
  }
  const allowed = new Set((st.allowed || []).map((a) => a.external_id));
  const results = h("div", { class: "kt-stack" });
  const allowedBox = h("div", { class: "kt-stack", style: "gap:8px" });
  const search = h("input", { id: "psearch", class: "kt-input kt-input--search", type: "search", value: plexState.filter,
    placeholder: "Search Plex, or filter what's shown", enterkeyhint: "search" });

  const drawAllowed = (list) => fill(allowedBox, list.length ? [h("h2", { class: "kt-label" }, `Already allowed (${list.length})`),
    h("div", { class: "kt-list" }, list.map((a) => h("a", { class: "kt-list__row", href: `#channel/${a.id}` },
      plexPoster(a.external_id, a.title, "poster--sm"),
      h("span", { class: "kt-list__text" }, a.title, h("span", { class: "kt-muted" }, `${a.ready} ready${a.unplayable ? ` · ${a.unplayable} won't play` : ""} · ${a.profile_ids.length ? "for " + namesOf(a.profile_ids) : "nobody yet"}`)),
      h("button", { class: "kt-btn kt-btn--danger", type: "button", onclick: (e) => { e.preventDefault(); run(async () => { await api(`/plex/containers/${a.id}`, { method: "DELETE" }); toast(`${a.title} removed. Plex keeps the files.`); refresh(); }); } }, "Remove"))))] : []);
  const refresh = () => api("/plex").then((fresh) => { allowed.clear(); (fresh.allowed || []).forEach((a) => allowed.add(a.external_id)); drawAllowed(fresh.allowed || []); drawResults(); }).catch(() => {});

  const drawResults = () => {
    if (!plexState.items) return fill(results, h("p", { class: "kt-muted", style: "margin:0" }, "Search, or open a library above."));
    const q = plexState.filter.toLowerCase();
    const shown = plexState.items.filter((m) => !q || m.title.toLowerCase().includes(q));
    fill(results,
      h("div", { class: "kt-row", style: "justify-content:space-between" }, h("h2", { class: "kt-label", style: "margin:0" }, plexState.title),
        h("span", { class: "kt-muted" }, `${shown.length} of ${plexState.items.length}`)),
      shown.length ? h("div", { class: "poster-grid" }, shown.slice(0, 300).map((m) => plexCard(m, allowed, refresh))) : h("div", { class: "empty" }, "Nothing matches."),
      shown.length > 300 ? h("p", { class: "kt-muted", style: "margin:0" }, "Showing the first 300. Type to narrow it down.") : null);
  };
  const load = (title, path) => run(async () => {
    plexState.title = title;
    plexState.items = [];
    fill(results, loadingLine(`Loading ${title}…`), h("div", { class: "poster-grid" }, Array.from({ length: 8 }, () =>
      h("div", { class: "poster-card" }, skel("poster"), skel("kt-skel--title")))));
    try { plexState.items = await api(path); } catch (e) { plexState.items = null; drawResults(); throw e; }
    drawResults();
  });
  search.addEventListener("input", () => { plexState.filter = search.value.trim(); drawResults(); });

  const sections = await api("/plex/sections").catch(() => []);
  screen("Browse Plex", { back: "add" },
    h("p", { class: "kt-muted", style: "margin:0" }, "Nothing from Plex shows on the TVs until you allow it. Videos play straight from Plex; nothing is copied."),
    (st.unplayable || []).length ? h("div", { class: "kt-banner kt-banner--warn" }, h("span", {}, h("strong", {}, `${st.unplayable.length} allowed titles won't play on the TVs`), " as they are (for example 4K or DTS sound), so they are hidden. An optimized version in Plex fixes that.")) : null,
    h("form", { onsubmit: (e) => {
      e.preventDefault();
      const q = search.value.trim();
      if (q.length < 2) return toast("Type at least two letters.");
      plexState.filter = "";
      search.value = "";
      load(`Search: “${q}”`, "/plex/search?q=" + encodeURIComponent(q));
    } }, h("label", { for: "psearch", class: "sr" }, "Search Plex"), search),
    h("div", { class: "kt-row" }, sections.map((s) => [
      h("button", { class: "kt-chip", type: "button", onclick: () => load(s.title, `/plex/sections/${s.key}?kind=all`) }, s.title),
      h("button", { class: "kt-chip", type: "button", onclick: () => load(`${s.title}: collections`, `/plex/sections/${s.key}?kind=collections`) }, `${s.title}: collections`)])),
    forRow(),
    results,
    allowedBox);
  drawResults();
  drawAllowed(st.allowed || []);
}

async function viewPlexConnect() {
  const st = await api("/plex");
  const url = h("input", { id: "purl", class: "kt-input", value: st.url || "", placeholder: "http://192.168.1.10:32400" });
  const token = h("input", { id: "ptoken", class: "kt-input", type: "password", autocomplete: "off", placeholder: st.connected ? "Saved. Needed again only if the address changes" : "Plex token" });
  const form = [
    h("div", { class: "kt-field" }, h("label", { for: "purl" }, "Plex address"), url),
    h("div", { class: "kt-field" }, h("label", { for: "ptoken" }, "Plex token"), token),
    h("button", { class: "kt-btn kt-btn--primary", type: "button", style: "align-self:flex-start", onclick: (e) => run(async () => {
      busy(e.currentTarget);
      try { await api("/plex", { method: "PUT", body: { url: url.value, token: token.value } }); } finally { busy(e.target, false); }
      toast("Connected");
      viewPlexConnect();
    }) }, st.connected ? "Save" : "Connect")];
  screen("Plex", { back: "settings", narrow: true },
    st.connected ? h("div", { class: "kt-list" }, row(`Connected to ${st.name}`, h("span", { class: "kt-tag kt-tag--ok" }, "On"), `${(st.allowed || []).length} shows and movies allowed`))
      : h("p", { style: "margin:0" }, st.error ? h("span", { class: "err" }, st.error) : "Connect Plex to bring shows and movies you already own into the boys' app. Nothing in Plex changes."),
    st.connected ? h("a", { class: "kt-btn kt-btn--primary", href: "#plex", style: "align-self:flex-start" }, "Browse and allow") : null,
    st.connected ? h("details", { class: "more-opts" }, h("summary", {}, "Change the connection"), h("div", { class: "kt-stack", style: "padding-top:12px" }, form)) : h("div", { class: "panel" }, form));
}

// #tvs/<code> comes from the QR code on the TV's pairing screen (ADR 0039): the code arrives filled in.
async function viewTvs(prefill = "") {
  const devices = await api("/devices");
  const code = h("input", { id: "code", class: "kt-input", inputmode: "numeric", maxlength: 7, placeholder: "123456", style: "font-size:22px; letter-spacing:.12em; text-align:center" });
  const name = h("input", { id: "tvname", class: "kt-input", placeholder: "Playroom TV" });
  code.value = prefill.replace(/\D/g, "").slice(0, 6);
  screen("TVs", { back: "settings" },
    devices.length ? h("div", { class: "kt-list" }, devices.map((d) => row(d.name, d.revoked ? h("span", { class: "kt-tag" }, "Removed")
      : h("button", { class: "kt-btn kt-btn--danger", type: "button", onclick: () => run(async () => { await api(`/devices/${d.id}`, { method: "DELETE" }); viewTvs(); }) }, "Remove"),
      d.last_seen ? `Seen ${ago(d.last_seen)}` : "Not seen yet"))) : h("div", { class: "kt-muted" }, "No TVs yet."),
    h("h2", { class: "kt-label" }, "Pair a new TV"),
    h("p", { class: "kt-muted", style: "margin:0" }, "Open the app on the TV. It shows a 6-digit code for 15 minutes."),
    h("div", { class: "kt-field" }, h("label", { for: "code" }, "Code on the TV"), code),
    h("div", { class: "kt-field" }, h("label", { for: "tvname" }, "Name"), name),
    h("button", { class: "kt-btn kt-btn--primary kt-btn--wide", type: "button", onclick: () => run(async () => {
      await api("/devices/pair", { method: "POST", body: { code: code.value.replace(/\D/g, ""), name: name.value.trim() || "TV" } });
      toast("TV paired");
      history.replaceState(null, "", "#tvs");  // a reload must not offer the used code again
      viewTvs();
    }) }, "Pair"));
  if (code.value) name.focus();
}

async function viewProfiles() {
  profiles = await api("/profiles");
  const name = h("input", { id: "pname", class: "kt-input", placeholder: "Name" });
  const kind = h("select", { id: "pkind", class: "kt-input" }, h("option", { value: "child" }, "Child"), h("option", { value: "guest" }, "Guest"), h("option", { value: "grownup" }, "Grown-up"));
  screen("Profiles", { back: "settings" },
    profiles.length ? h("div", { class: "kt-list" }, profiles.map((p) => h("a", { class: "kt-list__row", href: `#profile/${p.id}` }, profileAvatar(p),
      h("span", { class: "kt-list__text" }, p.name, h("span", { class: "kt-muted" }, { child: "Child", guest: "Guest", grownup: "Grown-up" }[p.kind])),
      h("span", { class: "kt-list__value" }, "Edit")))) : h("div", { class: "kt-muted" }, "Add a profile for each boy."),
    h("h2", { class: "kt-label" }, "Add a profile"),
    h("div", { class: "kt-field" }, h("label", { for: "pname" }, "Name"), name),
    h("div", { class: "kt-field" }, h("label", { for: "pkind" }, "Kind"), kind),
    h("button", { class: "kt-btn kt-btn--primary kt-btn--wide", type: "button", onclick: () => run(async () => {
      if (!name.value.trim()) throw new Error("Type a name first.");
      const r = await api("/profiles", { method: "POST", body: { name: name.value.trim(), kind: kind.value } });
      go(`profile/${r.id}`);
    }) }, "Add"));
}

async function viewProfile(id) {
  const [all, av, ai] = await Promise.all([api("/profiles"), api("/avatars"), api("/ai").catch(() => ({}))]);
  profiles = all;
  const p = all.find((x) => x.id === +id);
  if (!p) return go("profiles");
  let pick = p.avatar, color = p.avatar_color || av.colors[0], picksOn = !!p.picks_on;
  const custom = (pick || "").startsWith("custom:");
  const big = h("div", { class: "kt-stack center" });
  const drawBig = () => fill(big, profileAvatar({ ...p, avatar_color: color, avatar_url: pick === p.avatar ? p.avatar_url : pick ? `/avatars/${pick}.svg` : "" }, "huge-avatar"));
  const grid = h("div", { class: "av-grid" });
  const drawGrid = () => fill(grid, av.characters.map((c) => h("button", { type: "button", "aria-label": c, title: c, "aria-pressed": pick === c ? "true" : "false",
    onclick: () => { pick = c; drawGrid(); drawBig(); } }, profileAvatar({ avatar_url: `/avatars/${c}.svg`, avatar_color: color }, "kt-avatar--lg"))));
  const swatches = h("div", { class: "swatches" });
  const drawSw = () => fill(swatches, av.colors.map((c) => h("button", { type: "button", class: `av--${c}`, "aria-label": c, title: c, "aria-pressed": color === c ? "true" : "false",
    onclick: () => { color = c; drawSw(); drawGrid(); drawBig(); } })));
  drawBig(); drawGrid(); drawSw();
  const name = h("input", { id: "pname", class: "kt-input", value: p.name });
  const bday = h("input", { id: "pbday", class: "kt-input", type: "date", value: p.birthday || "" });
  const file = h("input", { type: "file", accept: "image/png,image/jpeg,image/webp,image/gif", class: "sr", id: "pfile" });
  file.addEventListener("change", () => run(async () => {
    const f = file.files[0];
    if (!f) return;
    const res = await fetch(`/api/admin/profiles/${p.id}/avatar-image`, { method: "POST", headers: { "Content-Type": f.type }, body: f });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "Upload failed.");
    await api(`/profiles/${p.id}`, { method: "PATCH", body: { avatar_color: color } });
    toast("Picture saved");
    viewProfile(id);
  }));
  screen(p.name, { back: `kid/${p.id}` },
    big,
    h("h2", { class: "kt-label" }, "Character"),
    grid,
    h("div", { class: "kt-row" },
      h("label", { class: "kt-btn", for: "pfile", style: "cursor:pointer" }, custom ? "Change own picture" : "Use your own picture"), file,
      custom ? h("span", { class: "kt-tag kt-tag--ok" }, "Own picture in use") : null),
    h("p", { class: "kt-muted", style: "margin:0" }, "Your own picture: for example the character he already knows. Pick a character above to go back to one of ours."),
    h("h2", { class: "kt-label" }, "Colour"),
    swatches,
    h("h2", { class: "kt-label" }, "About"),
    h("div", { class: "kt-field" }, h("label", { for: "pname" }, "Name"), name),
    p.kind === "child" ? h("div", { class: "kt-field" }, h("label", { for: "pbday" }, "Birthday (optional)"), bday) : null,
    p.kind === "child" ? h("p", { class: "kt-muted", style: "margin:0" }, "Stays on this server. The AI only ever gets an age band like “3 to 5”, never a name or date.") : null,
    p.kind === "child" && ai.enabled ? h("div", { class: "kt-list" }, row("“Picked for you” row", switchBtn(picksOn, "Picked for you row", (v) => (picksOn = v)), "AI orders his approved videos")) : null,
    h("button", { class: "kt-btn kt-btn--primary kt-btn--wide", type: "button", onclick: (e) => run(async () => {
      busy(e.target);
      const body = { name: name.value.trim() || p.name, avatar_color: color, picks_on: picksOn };
      if (pick !== p.avatar) body.avatar = pick;
      if (p.kind === "child") body.birthday = bday.value || "";
      await api(`/profiles/${p.id}`, { method: "PATCH", body });
      toast("Saved");
      go(`kid/${p.id}`);
    }).finally(() => busy(e.target, false)) }, "Save"),
    h("button", { class: "kt-btn kt-btn--danger", type: "button", style: "align-self:flex-start", onclick: (e) => {
      const b = e.currentTarget;
      if (b.dataset.sure) return run(async () => { await api(`/profiles/${p.id}`, { method: "DELETE" }); go("profiles"); });
      b.dataset.sure = "1";
      b.textContent = "Tap again: deletes history too";
    } }, "Delete profile"));
}

// ---- AI through OpenRouter (ADR 0034) ------------------------------------------------------------------------------

async function viewAI() {
  const a = await api("/ai");
  const save = async (body, btn) => {
    busy(btn);
    try { await api("/ai", { method: "PUT", body }); } finally { busy(btn, false); }
  };
  const step = (n, title, done, ...body) => h("div", { class: "panel" },
    h("div", { class: "kt-row", style: "gap:10px; flex-wrap:nowrap" },
      h("span", { class: "step-num" + (done ? " step-num--done" : "") }, done ? icon("check") : String(n)),
      h("strong", { style: "font-size:17px" }, title)),
    ...body);

  // ---- step 1: the key ---------------------------------------------------------------------------------------------
  const key = h("input", { id: "aikey", class: "kt-input", type: "password", autocomplete: "off", spellcheck: "false",
    placeholder: a.key_saved ? "Saved. Paste a new one to replace it" : "sk-or-v1-…" });
  const step1 = step(1, "Your OpenRouter key", a.key_saved,
    a.key_saved ? h("div", { class: "kt-row" }, h("span", { class: "kt-tag kt-tag--ok" }, "Key saved"), h("span", { class: "kt-muted" }, "Stays on the server; this page never shows it again.")) :
      h("p", { class: "kt-muted", style: "margin:0" }, "Make one at openrouter.ai › Keys. It is checked with OpenRouter before it is saved."),
    h("div", { class: "kt-field" }, h("label", { for: "aikey", class: a.key_saved ? "sr" : null }, "Key"), key),
    h("div", { class: "kt-row" },
      h("button", { class: "kt-btn" + (a.key_saved ? "" : " kt-btn--primary"), type: "button", onclick: (e) => run(async () => {
        if (!key.value.trim()) throw new Error("Paste a key first.");
        await save({ key: key.value.trim() }, e.target);
        toast("Key checked and saved. Now pick a model.");
        viewAI();
      }) }, a.key_saved ? "Replace key" : "Check and save"),
      a.key_saved ? h("button", { class: "kt-btn kt-btn--quiet", type: "button", onclick: (e) => run(async () => {
        const b = e.target;
        if (!b.dataset.sure) { b.dataset.sure = "1"; b.textContent = "Tap again: AI turns off"; return; }
        await save({ clear_key: true }, b);
        toast("Key removed. AI is off.");
        viewAI();
      }) }, "Remove key") : null));

  // ---- step 2: the model, from OpenRouter's list ---------------------------------------------------------------------
  let models = null, chosen = a.model, filter = "", freeOnly = false;
  const search = h("input", { class: "kt-input kt-input--search", type: "search", placeholder: "Search models, e.g. gemini, claude, llama", "aria-label": "Search models" });
  const list = h("div", { class: "kt-list model-list" });
  const current = h("div", { class: "kt-muted" });
  const price = (m) => (m.free ? "Free" : `$${m.in_per_m} in · $${m.out_per_m} out`);
  const drawCurrent = () => {
    const m = models && models.find((x) => x.id === chosen);
    fill(current, models && !m ? h("span", { class: "err" }, `“${chosen}” isn't on OpenRouter any more. Pick another.`)
      : [h("strong", { style: "color:var(--ink)" }, m ? m.name : chosen), m ? ` · ${price(m)} per million tokens` : ""]);
  };
  const drawList = () => {
    if (!models) return;
    const q = filter.toLowerCase();
    const hits = models.filter((m) => (!freeOnly || m.free) && (!q || m.id.toLowerCase().includes(q) || m.name.toLowerCase().includes(q)));
    const shown = hits.slice(0, 60);
    fill(list, shown.length ? shown.map((m) => h("button", { class: "kt-list__row model-row", type: "button", "aria-pressed": m.id === chosen ? "true" : "false",
      onclick: (e) => run(async () => {
        await save({ model: m.id }, e.currentTarget);
        chosen = m.id;
        drawCurrent(); drawList();
        toast(`Using ${m.name}`);
      }) },
      h("span", { class: "kt-list__text" }, m.name, h("span", { class: "kt-muted" }, `${m.id}${m.context ? ` · ${Math.round(m.context / 1000)}k context` : ""}`)),
      h("span", { class: "kt-list__value" }, price(m)),
      m.id === chosen ? icon("check") : null))
      : h("div", { class: "empty" }, "No model matches."),
      hits.length > shown.length ? h("div", { class: "kt-muted", style: "padding:12px 16px" }, `${hits.length - shown.length} more. Search to narrow the list.`) : null);
  };
  search.addEventListener("input", () => { filter = search.value.trim(); drawList(); });
  const freeBtn = h("button", { class: "kt-chip", type: "button", "aria-pressed": "false", onclick: () => { freeOnly = !freeOnly; freeBtn.setAttribute("aria-pressed", String(freeOnly)); drawList(); } }, "Free only");
  const loadModels = (refresh, btn) => run(async () => {
    busy(btn);
    fill(list, loadingLine("Loading models from OpenRouter…"), skel("kt-skel--line", "margin:12px 16px"), skel("kt-skel--line", "margin:12px 16px; width:70%"));
    try {
      models = await api("/ai/models" + (refresh ? "?refresh=1" : ""));
      drawCurrent(); drawList();
    } catch (err) {
      fill(list, h("div", { class: "err", style: "padding:12px 16px" }, err.message));
      throw err;
    } finally { busy(btn, false); }
  });
  const step2 = a.key_saved
    ? step(2, "Pick a model", !!a.model,
        current,
        h("p", { class: "kt-muted", style: "margin:0" }, "Cheapest first. A small, cheap model is plenty: it only arranges rows and suggests channels."),
        search,
        h("div", { class: "kt-row" }, freeBtn, h("button", { class: "kt-btn kt-btn--quiet", type: "button", onclick: (e) => loadModels(true, e.currentTarget) }, "Reload list")),
        list)
    : step(2, "Pick a model", false, h("p", { class: "kt-muted", style: "margin:0" }, "Save a key first. Then the models on your OpenRouter account load here."));

  // ---- step 3: cap and switch on -----------------------------------------------------------------------------------
  const cap = h("input", { id: "aicap", class: "kt-input num", type: "number", min: 0, step: "0.5", value: a.cap_usd });
  const pct = a.cap_usd ? Math.min(100, (a.spent_usd / a.cap_usd) * 100) : 100;
  const step3 = step(3, "Spending cap, then switch on", a.enabled,
    h("div", { class: "kt-list" },
      row(h("label", { for: "aicap" }, "Most to spend a month, $"), cap),
      row("Use AI", switchBtn(a.enabled, "Use AI", (v) => run(async () => {
        await save({ enabled: v, cap_usd: +cap.value || 0 });
        toast(v ? "AI is on" : "AI is off");
        viewAI();
      })), a.key_saved ? "Suggestions for you, a “Picked for you” row for the boys" : "Save a key first")),
    h("div", { class: "kt-row" },
      h("button", { class: "kt-btn", type: "button", onclick: (e) => run(async () => { await save({ cap_usd: +cap.value || 0 }, e.target); toast("Cap saved"); viewAI(); }) }, "Save cap"),
      a.key_saved ? h("button", { class: "kt-btn kt-btn--quiet", type: "button", onclick: (e) => run(async () => { busy(e.target); try { await api("/ai/try", { method: "POST" }); toast("The model answered. It works."); viewAI(); } finally { busy(e.target, false); } }) }, "Try it") : null),
    h("div", { class: "kt-row", style: "justify-content:space-between" }, h("span", {}, `$${a.spent_usd.toFixed(2)} of $${a.cap_usd.toFixed(2)} this month`), h("span", { class: "kt-muted" }, `${a.calls_this_month} calls${a.failed_this_month ? `, ${a.failed_this_month} failed` : ""}`)),
    h("div", { class: "kt-bar" + (a.over_cap ? " kt-bar--low" : "") }, h("i", { style: `width:${pct}%` })),
    a.over_cap ? h("div", { class: "err" }, "The cap is reached. AI jobs wait for next month; the boys' rows fall back to the usual order.") : null,
    a.last_call && !a.last_call.ok ? h("div", { class: "err" }, `Last call failed: ${a.last_call.error}`) : null);

  screen("AI", { back: "settings" }, step1, step2, step3,
    a.enabled ? [h("h2", { class: "kt-label" }, "Run now"),
      h("div", { class: "kt-row" },
        h("button", { class: "kt-btn", type: "button", onclick: (e) => run(async () => { busy(e.target); await api("/background-jobs/ai-suggest/run", { method: "POST" }); kickActivity(); toast("Looking for suggestions. They land in Add › Ideas."); }).finally(() => busy(e.target, false)) }, "Find suggestions"),
        h("button", { class: "kt-btn", type: "button", onclick: (e) => run(async () => { busy(e.target); await api("/background-jobs/ai-picks/run", { method: "POST" }); kickActivity(); toast("Rebuilding the boys' rows"); }).finally(() => busy(e.target, false)) }, "Rebuild “Picked for you”"))] : null,
    h("h2", { class: "kt-label" }, "What is sent"),
    h("p", { class: "kt-muted", style: "margin:0" }, "Video titles, channel names and play counts. The boys are “Child A” and “Child B”, with an age band at most: never names or birthdays. The AI can only reorder videos you already approved; it can't add or unhide anything."),
    h("p", { class: "kt-muted", style: "margin:0" }, "Switch the row off per boy in Kids › Picture and name."));
  if (a.key_saved) loadModels(false);
}

async function viewIdeas() {
  const list = await api("/suggestions");
  const who = (ids) => (ids.length ? "For " + namesOf(ids) : "");
  const dismiss = (sg) => run(async () => { await api(`/suggestions/${sg.id}/dismiss`, { method: "POST" }); viewIdeas(); });
  const cards = list.map((sg) => {
    const meta = [sg.kind === "channel" ? "Channel" : sg.channel_title, who(sg.for_profiles)].filter(Boolean).join(" · ");
    if (sg.kind === "channel") {
      return h("div", { class: "kt-video" },
        sg.has_pic ? chanAvatar(sg.external_id, "", sg.title, "kt-avatar--lg") : laterAvatar(sg.external_id, sg.title, "kt-avatar--lg"),
        h("div", { class: "kt-video__body" }, h("div", { class: "kt-video__title" }, sg.title), h("div", { class: "kt-muted" }, meta),
          sg.reason ? h("div", { class: "kt-muted suggest-why" }, sg.reason) : null,
          h("div", { class: "kt-row" }, h("a", { class: "kt-btn kt-btn--primary kt-btn--sm", href: "#subscribe/" + encodeURIComponent(sg.url) }, "Look and subscribe"),
            h("button", { class: "kt-btn kt-btn--sm", type: "button", onclick: () => dismiss(sg) }, "No thanks"))));
    }
    const v = { external_id: sg.external_id, url: sg.url, title: sg.title, thumb_url: sg.thumb_url, duration_s: sg.duration_s, channel_title: sg.channel_title };
    return h("div", { class: "kt-stack", style: "gap:6px" }, videoRow(v, { right: [addButtons(v), h("button", { class: "kt-btn kt-btn--sm", type: "button", onclick: () => dismiss(sg) }, "No thanks")] }),
      sg.reason ? h("div", { class: "kt-muted suggest-why" }, sg.reason) : null);
  });
  screen("Ideas", { back: "add" },
    list.length ? [h("p", { class: "kt-muted", style: "margin:0" }, "Suggested by the AI and checked on YouTube. Nothing is added until you add it."), forRow(), cards]
      : h("div", { class: "empty-state" }, h("h2", { class: "h-display" }, "No ideas right now"),
          h("p", { style: "margin:0" }, "With AI on, new ideas arrive once a week. You can also ask for some now."),
          h("a", { class: "kt-btn", href: "#ai" }, "Open AI settings")));
  watchPictures(app);
}

// ---- Import from YouTube Kids (ADR 0035) ---------------------------------------------------------------------------

async function viewImport() {
  const open = await api("/imports/open");
  if (open.id) return go(`import/${open.id}`);
  let mode = "paste";
  const box = h("div", { class: "kt-stack" });
  const text = h("textarea", { id: "imptext", class: "kt-input", placeholder: "https://www.youtube.com/@SuperSimpleSongs\nhttps://www.youtube.com/watch?v=…" });
  const plist = h("input", { id: "impplist", class: "kt-input", placeholder: "https://www.youtube.com/playlist?list=…" });
  // One file box per kid, so what comes out of his account is offered for him; the last one is for everybody.
  const kidsHere = profiles.filter((p) => p.kind === "child");
  const fileBox = (key, label, ids) => ({ label, ids, id: `impfile${key}`,
    input: h("input", { id: `impfile${key}`, type: "file", multiple: true, accept: ".csv,.html,.json,text/csv,text/html,application/json", class: "kt-input", style: "padding-top:8px" }) });
  const fileBoxes = [...kidsHere.map((p) => fileBox(p.id, `From ${p.name}'s account`, [p.id])),
    fileBox("all", kidsHere.length ? "From a shared account (for everyone)" : "Takeout files", [])];
  const minWatches = h("select", { id: "impmin", class: "kt-input" }, [2, 3, 5, 10].map((n) => h("option", { value: n, selected: n === 3 }, `${n} times or more`)));
  const seg = h("div", { class: "seg", role: "group", "aria-label": "How" });
  const drawSeg = () => fill(seg, [["paste", "Paste links"], ["takeout", "Takeout file"], ["playlist", "A playlist"]].map(([v, t]) =>
    h("button", { type: "button", "aria-pressed": mode === v ? "true" : "false", onclick: () => { mode = v; drawSeg(); drawBox(); } }, t)));
  const drawBox = () => fill(box,
    mode === "paste" ? [h("div", { class: "kt-field" }, h("label", { for: "imptext" }, "Channel and video links, any mix"), text),
      h("p", { class: "kt-muted", style: "margin:0" }, "On a computer, open YouTube Kids › Settings › the boy › Approved content, then copy the channels and videos. Links, @handles, anything with links in it works.")]
    : mode === "takeout" ? [
      h("p", { class: "kt-muted", style: "margin:0" }, "From takeout.google.com › YouTube, for the account the boys watched on: subscriptions.csv, a playlist CSV and watch-history.html. Choose several files at once if you like."),
      fileBoxes.map((b) => h("div", { class: "kt-field" }, h("label", { for: b.id }, b.label), b.input)),
      h("div", { class: "kt-field" }, h("label", { for: "impmin" }, "From a watch history, bring in videos watched"), minWatches),
      h("p", { class: "kt-muted", style: "margin:0" }, "A watch history only lists links, so each video is looked up, slowly: about a thousand videos take two to three hours. They come back grouped by channel. The search history isn't used.")]
    : [h("div", { class: "kt-field" }, h("label", { for: "impplist" }, "Playlist link"), plist),
      h("p", { class: "kt-muted", style: "margin:0" }, "Build one playlist of everything approved on your phone, then paste its link. Every video in it comes in.")]);
  drawSeg(); drawBox();
  screen("Import", { back: "add" },
    h("p", { style: "margin:0" }, "Bring in what the boys already have approved. You check everything before it's added."),
    seg, box,
    h("button", { class: "kt-btn kt-btn--primary kt-btn--wide", type: "button", onclick: (e) => run(async () => {
      busy(e.target);
      try {
        let body;
        if (mode === "takeout") {
          const files = [];
          for (const b of fileBoxes) for (const f of b.input.files) files.push({ text: await f.text(), profile_ids: b.ids });
          if (!files.length) throw new Error("Choose the Takeout files first.");
          body = { source: "takeout", files: files.filter((f) => f.text.trim()), min_watches: Number(minWatches.value) };
        } else {
          body = { source: mode, text: mode === "paste" ? text.value : plist.value };
          if (!body.text.trim()) throw new Error("Nothing to import yet.");
        }
        const r = await api("/import", { method: "POST", body });
        kickActivity();
        go(`import/${r.id}`);
      } finally { busy(e.target, false); }
    }) }, "Read the links"));
}

const importChoice = {};

// The finish message: what is downloading now and what is not, so "nothing came in" is never a surprise.
function importFinished(res, counts) {
  const n = (k) => (res && res[k]) || 0, s = (x, one, many) => `${x} ${x === 1 ? one : many}`;
  const lines = res ? [
    n("videos") ? [`${s(n("videos"), "video", "videos")} added. `, h("a", { href: "#downloads" }, "Downloading now"), ", one at a time."] : null,
    n("channels_now") ? `${s(n("channels_now"), "channel", "channels")} subscribed: their latest videos are downloading now, new ones come in later.` : null,
    n("channels_new") ? `${s(n("channels_new"), "channel", "channels")} subscribed for new uploads only: nothing from ${n("channels_new") === 1 ? "it" : "them"} downloads until ${n("channels_new") === 1 ? "it posts" : "they post"} something new.` : null,
    n("channels_allowed") ? `${s(n("channels_allowed"), "channel", "channels")} allowed for the boys you chose: nothing downloads from ${n("channels_allowed") === 1 ? "it" : "them"} until you add videos.` : null,
    n("waiting") ? [`${s(n("waiting"), "video waits", "videos wait")} in `, h("a", { href: "#approve" }, "Approve"), " because of a blocked word."] : null,
    n("skipped") ? `${n("skipped")} skipped.` : null,
    n("failed") ? `${n("failed")} couldn't be added (below).` : null,
  ].filter(Boolean) : [`${counts.done} added, ${counts.skipped} skipped${counts.failed ? `, ${counts.failed} failed` : ""}.`];
  return h("div", { class: "kt-banner kt-banner--ok" }, h("div", { class: "kt-stack", style: "gap:4px" },
    h("strong", {}, "Import finished."), lines.length ? lines.map((l) => h("span", {}, l)) : h("span", {}, "Nothing was added.")));
}

// Rows that couldn't be read: the ones YouTube refused for a moment can be read again; the gone ones are listed apart.
function importFailures(id, failed) {
  if (!failed.length) return null;
  const again = failed.filter((r) => !r.gone), gone = failed.filter((r) => r.gone);
  return [
    again.length ? [h("h2", { class: "kt-label" }, `Couldn't read (${again.length})`),
      h("p", { class: "kt-muted", style: "margin:0" }, "YouTube sometimes refuses a link for a moment when many are read in a row. Most of these work when read again."),
      h("button", { class: "kt-btn kt-btn--primary", type: "button", style: "align-self:flex-start", onclick: (e) => run(async () => {
        busy(e.currentTarget);
        const r = await api(`/import/${id}/retry`, { method: "POST" });
        toast(`Reading ${r.retrying} again. They come back here to choose from.`);
        kickActivity();
        viewImportRun(id);
      }) }, again.length === 1 ? "Try it again" : `Try these ${again.length} again`),
      h("div", { class: "kt-list" }, again.map((r) => row(r.title || r.url, null, r.error)))] : null,
    gone.length ? [h("h2", { class: "kt-label" }, `Gone from YouTube (${gone.length})`),
      h("div", { class: "kt-list" }, gone.map((r) => row(r.title || r.url, null, r.error)))] : null,
  ];
}

async function viewImportRun(id) {
  const children = profiles.filter((p) => p.kind === "child").map((p) => p.id);
  let opts = { mode: "new", last_n: 10, trusted: false };
  const body = h("div", { class: "kt-stack", style: "gap:16px" }, loadingLine("Loading the import…"), skelRows(3));
  screen("Import", { back: "add", action: h("button", { class: "kt-btn kt-btn--quiet", type: "button", onclick: (e) => {
    const b = e.currentTarget;
    if (!b.dataset.sure) { b.dataset.sure = "1"; b.textContent = "Tap again to cancel"; return; }
    run(async () => { await api(`/import/${id}`, { method: "DELETE" }); go("import"); });
  } }, "Cancel") }, body);
  let floor = 0; // leave out channels found in the watch history that were watched fewer times than this
  const openGroups = new Set();
  const seenStates = new Set();
  let last = null;
  const draw = async () => paint(await api(`/import/${id}`));
  // Choices are kept in the page, so a tap in review paints again from what was fetched: a watch history is
  // over a thousand rows.
  const paint = (d) => {
    last = d;
    const imp = d.import, rows = d.rows;
    // Looked at: the activity pill stops pointing here (once per state, so a finish after review counts again).
    if ((imp.state === "review" || imp.state === "done") && !seenStates.has(imp.state)) {
      seenStates.add(imp.state);
      api(`/import/${id}/seen`, { method: "POST" }).then(kickActivity).catch(() => {});
    }
    const read = rows.filter((r) => r.state === "read");
    if (imp.state === "reading") {
      const { done, total } = d.progress;
      fill(body, loadingLine(d.note || "Reading the links…"),
        h("div", { class: "kt-bar" }, h("i", { style: `width:${total ? Math.round((done / total) * 100) : 5}%` })),
        h("p", { class: "kt-muted", style: "margin:0" }, `${done} of ${total} read. Slowly on purpose, so YouTube doesn't mind. You can leave this page; it carries on.`),
        rows.map((r) => row(r.title, null, r.kind === "channel" ? "Channel" : r.channel_title)));
      return true;
    }
    if (imp.state === "applying" || imp.state === "done") {
      const counts = { done: 0, skipped: 0, failed: 0 };
      rows.forEach((r) => { if (counts[r.state] !== undefined) counts[r.state]++; });
      fill(body, imp.state === "applying" ? loadingLine(d.note || "Adding…") : importFinished(d.result, counts),
        imp.state === "done" ? importFailures(id, rows.filter((r) => r.state === "failed")) : null,
        imp.state === "done" ? h("div", { class: "kt-row" }, h("a", { class: "kt-btn kt-btn--primary", href: "#library" }, "Open the library"), h("a", { class: "kt-btn", href: "#import" }, "Import more")) : null);
      return imp.state === "applying";
    }
    // review
    const failed = rows.filter((r) => r.state === "failed");
    // Videos from a watch history sit under their channel (the most watched channel first); the rest are loose.
    const chans = read.filter((r) => r.kind === "channel").sort((a, b) => b.watches - a.watches);
    const byChan = new Map(chans.map((c) => [c.external_id, []]));
    const loose = [];
    for (const r of read) if (r.kind === "video") ((r.watches > 0 && byChan.get(r.channel_id)) || loose).push(r);
    const watched = (c) => byChan.get(c.external_id) || [];
    const nVideos = read.length - chans.length;
    // A channel the parent named (subscriptions.csv, a pasted link) was looked up and has a video count; one that
    // only turned up in the watch history was not.
    const named = (c) => c.video_count > 0 || !watched(c).length;
    // A channel is: subscribe, "videos" (only its watched videos; the channel itself is left alone), approve (the
    // channel, nothing downloaded) or skip. A video is approve or skip.
    const choiceFor = (r) => (importChoice[r.id] ||= {
      profile_ids: [...(r.profile_ids.length ? r.profile_ids : children)],
      action: r.kind !== "channel" ? (r.in_library ? "skip" : "approve")
        : named(r) && !r.in_library ? "subscribe"
        : watched(r).some((v) => !v.in_library) ? "videos" : "skip" });
    const act = (c) => {
      const ch = choiceFor(c);
      return floor && !ch.byHand && !named(c) && c.watches < floor ? "skip" : ch.action;
    };
    const vidAct = (v, c) => (c && act(c) === "skip" ? "skip" : choiceFor(v).action);
    const press = (on, label, onclick) => h("button", { type: "button", "aria-pressed": on ? "true" : "false", onclick }, label);
    const pick = (r, val, label, on) => press(on ?? choiceFor(r).action === val, label, () => { Object.assign(choiceFor(r), { action: val, byHand: true }); paint(last); });
    const who = (r, also = []) => profileChips(choiceFor(r).profile_ids, (ids) => [r, ...also].forEach((x) => (choiceFor(x).profile_ids = [...ids])));
    const times = (n) => `watched ${n} ${n === 1 ? "time" : "times"}`;
    const vidEl = (v, c) => h("div", { class: c ? "import-row import-row--sub" : "import-row" },
      thumb(v.thumb_url, { time: v.duration_s }),
      h("div", { class: "kt-video__body" },
        h("div", { class: "kt-video__title" }, v.title),
        h("div", { class: "kt-muted" }, [c ? null : v.channel_title, v.watches ? times(v.watches) : null, v.in_library ? "already in the library" : null].filter(Boolean).join(" · ")),
        c && act(c) === "skip" ? null : h("div", { class: "seg" }, pick(v, "approve", "Approve"), pick(v, "skip", "Skip")),
        !c && choiceFor(v).action !== "skip" ? who(v) : null));
    const chanEl = (c) => {
      const vids = watched(c), a = act(c), open = openGroups.has(c.id);
      return h("div", { class: "import-row" },
        c.has_pic ? chanAvatar(c.channel_id, c.thumb_url, c.title, "kt-avatar--lg") : chanAvatar("", c.thumb_url, c.title, "kt-avatar--lg"),
        h("div", { class: "kt-video__body" },
          h("div", { class: "kt-video__title" }, c.title),
          h("div", { class: "kt-muted" }, [c.video_count ? `Channel · ${c.video_count >= 50 ? "50+" : c.video_count} videos` : vids.length ? null : "Channel",
            vids.length ? `${vids.length} ${vids.length === 1 ? "video" : "videos"} ${times(c.watches)}` : null, c.in_library ? "already in the library" : null].filter(Boolean).join(" · ")),
          h("div", { class: "seg" }, pick(c, "subscribe", "Subscribe", a === "subscribe"),
            vids.length ? pick(c, "videos", "Just the videos", a === "videos") : pick(c, "approve", "Approve only", a === "approve"), pick(c, "skip", "Skip", a === "skip")),
          a !== "skip" ? who(c, vids) : null,
          vids.length ? h("button", { class: "kt-btn kt-btn--quiet kt-btn--sm", type: "button", style: "align-self:flex-start", "aria-expanded": String(open),
            onclick: () => { open ? openGroups.delete(c.id) : openGroups.add(c.id); paint(last); } }, open ? "Hide the videos" : `Show the ${vids.length === 1 ? "video" : `${vids.length} videos`}`) : null,
          open ? h("div", { class: "import-vids" }, vids.map((v) => vidEl(v, c))) : null));
    };
    const subs = chans.filter((c) => act(c) === "subscribe").length, only = chans.filter((c) => act(c) === "approve").length;
    const takes = loose.filter((v) => vidAct(v) !== "skip").length + chans.reduce((sum, c) => sum + watched(c).filter((v) => vidAct(v, c) !== "skip").length, 0);
    const n = subs + only + takes;
    const fromHistory = chans.some((c) => !named(c));
    const modeSel = h("select", { id: "impmode", class: "kt-input", onchange: (e) => (opts.mode = e.target.value) },
      h("option", { value: "new", selected: opts.mode === "new" }, "New uploads only"), h("option", { value: "last", selected: opts.mode === "last" }, "The latest 10 too"));
    const floorSel = h("select", { id: "impfloor", class: "kt-input", onchange: (e) => { floor = Number(e.target.value); paint(last); } },
      [[0, "Keep them all"], [10, "Under 10 watches"], [25, "Under 25 watches"], [50, "Under 50 watches"], [100, "Under 100 watches"]].map(([v, t]) => h("option", { value: v, selected: floor === v }, t)));
    const res = d.result;
    fill(body,
      res && res.stopped_after != null ? h("div", { class: "kt-banner kt-banner--warn" }, h("span", {},
        h("strong", {}, `Stopped after adding ${res.stopped_after} of ${res.of}. `),
        "Those are in. The rest are below: choose again and add them, or cancel.")) : null,
      h("p", { style: "margin:0" }, `${chans.length} ${chans.length === 1 ? "channel" : "channels"} and ${nVideos} ${nVideos === 1 ? "video" : "videos"} found${failed.length ? `, ${failed.length} couldn't be read` : ""}. Choose what to bring in and who it's for. Everything added counts as approved.`),
      imp.note ? h("p", { class: "kt-muted", style: "margin:0" }, imp.note) : null,
      chans.length ? [h("h2", { class: "kt-label" }, `Channels (${chans.length})`),
        h("div", { class: "kt-list" },
          row(h("label", { for: "impmode" }, "Subscribed channels download"), modeSel),
          row("Approve their new videos without asking", switchBtn(opts.trusted, "Trusted", (v) => (opts.trusted = v)), "Off: new videos wait in Approve"),
          fromHistory ? row(h("label", { for: "impfloor" }, "Leave out channels from the watch history"), floorSel, "Counts every watch of the channel's videos here. A channel you chose by hand stays as you set it") : null),
        h("p", { class: "kt-muted", style: "margin:0" }, fromHistory
          ? "“Just the videos” downloads the watched videos and leaves the channel alone. “Subscribe” brings those in and follows the channel too."
          : "“Approve only” adds the channel for the boys without downloading anything yet."),
        h("div", { class: "panel", style: "padding-top:0; padding-bottom:0" }, chans.map(chanEl))] : null,
      loose.length ? [h("h2", { class: "kt-label" }, `Videos (${loose.length})`), h("div", { class: "panel", style: "padding-top:0; padding-bottom:0" }, loose.map((v) => vidEl(v)))] : null,
      importFailures(id, failed),
      n ? h("p", { style: "margin:0" }, [takes ? `${takes} ${takes === 1 ? "video" : "videos"} to download` : null, subs ? `${subs} ${subs === 1 ? "channel" : "channels"} to subscribe to` : null, only ? `${only} approved without downloading` : null].filter(Boolean).join(", ") + ".") : null,
      h("button", { class: "kt-btn kt-btn--primary kt-btn--wide", type: "button", disabled: !n, onclick: (e) => run(async () => {
        busy(e.target);
        const choices = [];
        const send = (r, action) => choices.push({ row_id: r.id, action, profile_ids: choiceFor(r).profile_ids, trusted: opts.trusted, mode: opts.mode, last_n: 10 });
        for (const c of chans) {
          send(c, act(c) === "videos" ? "skip" : act(c));
          for (const v of watched(c)) send(v, vidAct(v, c));
        }
        for (const v of loose) send(v, vidAct(v));
        await api(`/import/${id}/apply`, { method: "POST", body: { choices } });
        kickActivity();
        draw();
        timer = setInterval(() => { if (location.hash === `#import/${id}`) draw().then((again) => { if (!again) clearInterval(timer); }).catch(() => {}); }, 3000);
      }) }, n ? `Add ${n}` : "Nothing chosen"),
      h("p", { class: "kt-muted", style: "margin:0" }, "Subscribing to many channels is paced: a few downloads a day per channel."));
    watchPictures(body);
    return false;
  };
  const again = await draw();
  if (again) timer = setInterval(() => { if (location.hash === `#import/${id}`) draw().then((more) => { if (!more) clearInterval(timer); }).catch(() => {}); }, 2500);
}

async function viewSafety() {
  const st = await api("/settings");
  const words = h("input", { id: "words", class: "kt-input", value: st.blocked_words.join(", ") });
  const cats = [["sponsor", "Sponsor reads"], ["selfpromo", "Plugs for their own stuff"], ["interaction", "“Like and subscribe”"], ["intro", "Intros"], ["outro", "Outros and end cards"]];
  const on = new Set(st.skip_categories);
  screen("Safety", { back: "settings" },
    h("h2", { class: "kt-label" }, "Blocked words"),
    h("div", { class: "kt-field" }, h("label", { for: "words" }, "Commas between words or phrases"), words),
    h("p", { class: "kt-muted", style: "margin:0" }, "Checked against titles and descriptions. A match waits in Approve, even on a channel you always approve."),
    h("h2", { class: "kt-label" }, "Skip inside videos"),
    h("div", { class: "kt-list" }, cats.map(([k, label]) => row(label, switchBtn(on.has(k), label, (v) => (v ? on.add(k) : on.delete(k)))))),
    h("p", { class: "kt-muted", style: "margin:0" }, "From SponsorBlock. Applies to videos downloaded from now on."),
    h("button", { class: "kt-btn kt-btn--primary kt-btn--wide", type: "button", onclick: () => run(async () => {
      await api("/settings", { method: "PUT", body: { blocked_words: words.value.split(","), skip_categories: [...on] } });
      toast("Saved");
      go("settings");
    }) }, "Save"));
}

async function viewHomeAssistant() {
  const a = await api("/automation");
  const keyBox = h("code", { style: "word-break:break-all; user-select:all" }, a.key || "No key yet");
  const base = `${location.origin}/api/automation/v1`;
  screen("Home Assistant", { back: "settings" },
    h("h2", { class: "kt-label" }, "Vacation mode"),
    h("div", { class: "kt-list" }, row("Use weekend time every day", switchBtn(a.vacation_mode, "Vacation mode", (v) => run(async () => {
      await api("/automation/vacation", { method: "POST", body: { on: v } });
      toast(v ? "Vacation mode on" : "Vacation mode off");
    })), "Home Assistant can switch this too")),
    h("h2", { class: "kt-label" }, "Key for Home Assistant"),
    h("div", { class: "panel" },
      keyBox,
      h("div", { class: "kt-row" },
        a.key ? h("button", { class: "kt-btn", type: "button", onclick: () => navigator.clipboard.writeText(keyBox.textContent).then(() => toast("Copied"), () => toast("Select the key and copy it")) }, "Copy") : null,
        h("button", { class: "kt-btn kt-btn--quiet", type: "button", onclick: () => run(async () => {
          const r = await api("/automation/key", { method: "POST" });
          keyBox.textContent = r.key;
          toast(a.key ? "New key made. The old one no longer works." : "Key made");
          a.key = r.key;
        }) }, a.key ? "Make a new key" : "Make a key"))),
    h("p", { class: "kt-muted", style: "margin:0" }, "Send it as “Authorization: Bearer <key>”. The example Home Assistant setup is in the project at docs/home-assistant/kidtube.yaml."),
    h("h2", { class: "kt-label" }, "Addresses"),
    h("div", { class: "kt-list" },
      row("Status (sensor)", null, `GET ${base}/status`),
      row("Add minutes, limit, last one, end now, unlock", null, `POST ${base}/profiles/<id>/extra|limit|lastone|lock|unlock`),
      row("Everything off", null, `POST ${base}/all/lock`),
      row("Vacation mode", null, `POST ${base}/vacation  {"on": true}`)));
}

function viewPassword() {
  const cur = h("input", { id: "cur", class: "kt-input", type: "password", autocomplete: "current-password" });
  const nw = h("input", { id: "new", class: "kt-input", type: "password", autocomplete: "new-password", minlength: 6 });
  screen("Change password", { back: "settings" },
    h("div", { class: "kt-field" }, h("label", { for: "cur" }, "Current password"), cur),
    h("div", { class: "kt-field" }, h("label", { for: "new" }, "New password"), nw),
    h("button", { class: "kt-btn kt-btn--primary kt-btn--wide", type: "button", onclick: () => run(async () => {
      await api("/auth/change", { method: "POST", body: { current: cur.value, new: nw.value } });
      toast("Password changed");
      go("settings");
    }) }, "Change"));
}

// ---- router -------------------------------------------------------------------------------------------------------

const TAB_OF = {
  library: "library", find: "library", add: "library", subscribe: "library", import: "library", plex: "library", ideas: "library",
  channel: "library", "channel-settings": "library", video: "library",
  approve: "approve",
  kids: "kids", kid: "kids", limits: "kids", reports: "kids", profile: "kids",
  downloads: "downloads", storage: "downloads", jobs: "jobs",
};
// Screens that use the whole width on a computer; the rest are forms and stay a narrow column (ADR 0037).
const WIDE = new Set(["library", "find", "approve", "kids", "settings", "downloads", "jobs", "plex", "channel", "ideas"]);

async function route() {
  clearInterval(timer);
  let [name, a, b] = (location.hash.slice(1) || (profiles.length ? "library" : "profiles")).split("/");
  name = { inbox: "approve", more: "settings" }[name] || name;
  for (const el of nav.querySelectorAll("a")) el.toggleAttribute("aria-current", el.dataset.tab === (TAB_OF[name] || "settings"));
  for (const el of nav.querySelectorAll("a[aria-current]")) el.setAttribute("aria-current", "page");
  const views = {
    library: viewLibrary, find: () => viewFind(decodeURIComponent(a || "")), add: viewAddMenu,
    subscribe: () => viewSubscribe(decodeURIComponent(a || "")), import: () => (a ? viewImportRun(a) : viewImport()),
    plex: viewPlex, "plex-connect": viewPlexConnect, ideas: viewIdeas,
    channel: () => viewChannel(a, b || "library"), "channel-settings": () => viewSubscribe("", a), video: () => viewVideo(a),
    approve: viewApprove,
    kids: viewKids, kid: () => viewKid(a), limits: () => viewLimits(a), reports: () => { history.replaceState(null, "", `#kid/${a}`); return viewKid(a); },  // the old "This week" screen
    profiles: viewProfiles, profile: () => viewProfile(a), tvs: () => viewTvs(a || ""),
    settings: viewSettingsMenu, downloads: () => viewDownloads(), jobs: viewJobs, storage: () => { history.replaceState(null, "", "#downloads"); return viewDownloads(true); },  // the old Library size page
    safety: viewSafety,
    ai: viewAI, "home-assistant": viewHomeAssistant, appearance: viewAppearance, password: viewPassword,
  };
  app.toggleAttribute("data-wide", WIDE.has(name));
  // A slow screen shows placeholders instead of the old one (ADR 0031). Only until the screen draws itself: a
  // screen may draw at once and then keep waiting (a pasted link waits ~4 s for YouTube), and wiping it then left
  // the placeholders up for good, with the answer landing in a screen no longer on the page.
  const before = screensDrawn;
  const slow = setTimeout(() => { if (screensDrawn === before) fill(app, topBar(""), h("div", { class: "content" }, skelRows(4))); }, 250);
  await run(views[name] || viewLibrary);
  clearTimeout(slow);
}

async function start() {
  nav.hidden = false;
  profiles = (await run(() => api("/profiles"))) || [];
  setApproveDot();
  window.onhashchange = route;
  route();
  pollActivity();
}

nav.addEventListener("click", (e) => { const a = e.target.closest("a[data-tab]"); if (a) go(a.dataset.tab); });
signIn().catch((e) => toast(e.message));
