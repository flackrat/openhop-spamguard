// SpamGuard field check: paste into the browser console (or a browser automation tool) while the
// SpamGuard page is open. It reads this SpamGuard's own status and evidence log and returns a short
// JSON summary of the last few hours: whether it stayed up, whether any blocked spam was forwarded,
// whether any genuine message was dropped, and what the spam map currently shows.
// Nothing is changed. The full result is kept in window.FC for follow-up questions.
// People's names are never read: the evidence log is fetched with names scrambled into consistent
// codes (N-xxxxxx, also inside messages that mention someone), and only the version, health and
// metrics parts of the status are kept, not its lists of recent senders or known people.
// Optional: set window.SG_SINCE (seconds since 1970) first to choose the start of the window.
(async () => {
  const now = Date.now() / 1000;
  const since = window.SG_SINCE || now - 12.5 * 3600;
  const key = (() => { try { return localStorage.getItem("sgkey") || ""; } catch (e) { return ""; } })();
  const t0 = performance.now();
  const full = await (await fetch("/status", { cache: "no-store" })).json();
  const d = { version: full.version, health: full.health, metrics: full.metrics,
              held: { length: (full.held || []).length }, blocks: { length: (full.blocks || []).length } };
  const ms = Math.round(performance.now() - t0);
  const m = d.metrics || {};
  const days = Math.max(1, Math.ceil((now - since) / 86400) + 1);
  let rows = [], evErr = null;
  try {
    const r = await fetch(`/evidence?days=${days}&scramble=1`, { headers: { "X-API-Key": key } });
    if (!r.ok) evErr = "evidence HTTP " + r.status;
    else rows = (await r.text()).split("\n").filter(Boolean).map(l => { try { return JSON.parse(l); } catch (e) { return null; } })
      .filter(x => x && x.ts >= since);
  } catch (e) { evErr = String(e).slice(0, 60); }
  const msgs = rows.filter(r => r.type === "msg");
  const verd = msgs.filter(r => "openhop_forwarded" in r);
  const spam = msgs.filter(r => r.caught_by);
  const leaks = verd.filter(r => r.caught_by && r.openhop_forwarded && !r.openhop_policy_dropped);
  const gdrop = verd.filter(r => !r.caught_by && r.openhop_policy_dropped && !r.openhop_forwarded);
  const starts = rows.filter(r => r.type === "settings" && r.why === "started");
  const codes = {};
  spam.forEach(r => { const c = (r.path || [])[0] || "direct"; codes[c] = (codes[c] || 0) + 1; });
  const kinds = {};
  spam.forEach(r => { const k = r.caught_kind || "?"; kinds[k] = (kinds[k] || 0) + 1; });
  const R = Math.PI / 180, me = m.me || {};
  const km = (a, b) => { const h = Math.sin((b[0] - a[0]) * R / 2) ** 2 + Math.cos(a[0] * R) * Math.cos(b[0] * R) * Math.sin((b[1] - a[1]) * R / 2) ** 2; return Math.round(12742 * Math.asin(Math.min(1, Math.sqrt(h)))); };
  const ents = m.entries || [];
  const sure = ents.filter(e => e.exact >= e.d7 / 2);
  const flags = [];
  if (evErr) flags.push(evErr);
  if (!d.health || !d.health.ok) flags.push("unhealthy: " + ((d.health || {}).error || "?"));
  if (leaks.length) flags.push(`${leaks.length} blocked spam forwarded`);
  if (gdrop.length) flags.push(`${gdrop.length} genuine dropped`);
  if (starts.length > 1) flags.push(`${starts.length} starts`);
  if (ms > 3000) flags.push(`status slow ${ms}ms`);
  if (m.map_working && starts.length && now - starts[starts.length - 1].ts > 1800) flags.push("map still working 30 min after start");
  if (!m.map_working && (m.advert_routes || 0) > 1000 && (m.learned || 0) < 200) flags.push("few codes learnt");
  const short = (s, n) => String(s || "").slice(0, n);
  const out = {
    window_h: Math.round((now - since) / 360) / 10, v: d.version, ms, flags,
    starts: starts.map(r => [new Date(r.ts * 1000).toTimeString().slice(0, 5), r.version]),
    msgs: msgs.length, spam: spam.length, kinds, leaks: leaks.length, gdrop: gdrop.length,
    leak_eg: leaks.slice(0, 2).map(r => [short(r.sender, 10), short(r.text, 28), (r.path || []).slice(0, 3).join(">")]),
    gdrop_eg: gdrop.slice(0, 2).map(r => [short(r.sender, 10), short(r.text, 28), (r.path || []).slice(0, 3).join(">")]),
    held: (d.held || []).length, blocks: (d.blocks || []).length,
    codes: Object.entries(codes).sort((a, b) => b[1] - a[1]).slice(0, 5),
    map: { working: !!m.map_working, learned: m.learned, adv: m.advert_routes, unplaced: (m.unplaced || {}).d7,
      sure: sure.slice(0, 4).map(e => [e.kind, e.code, short(e.name || (e.near || [])[0], 14), e.d7, me.lat != null ? km([me.lat, me.lon], [e.lat, e.lon]) : null]),
      guesses: ents.length - sure.length },
  };
  window.FC = { out, rows, status: d };
  let s = JSON.stringify(out);
  if (s.length > 950) { delete out.leak_eg; delete out.gdrop_eg; s = JSON.stringify(out); }
  return s;
})();
