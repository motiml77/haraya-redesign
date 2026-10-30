// המרקר שנמשך מתחת למילים בדוגמה, סימון השורה של המחשב הזה בטבלת ההורדות,
// והגרסה האחרונה ומונה ההורדות מ-GitHub. ההורדה הראשית היא תמיד לחלונות.
(function () {
  "use strict";
  document.documentElement.classList.add("js");

  // המרקר
  var blocks = document.querySelectorAll("[data-marks]");
  blocks.forEach(function (b) {
    b.querySelectorAll("mark").forEach(function (m, i) {
      m.style.setProperty("--d", (0.15 + i * 0.32) + "s");
    });
  });
  var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (still || !("IntersectionObserver" in window)) {
    blocks.forEach(function (b) { b.classList.add("on"); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("on"); io.unobserve(e.target); }
      });
    }, { threshold: 0.6 });
    // אחרי שני פריימים, כדי שהמצב הריק יצויר לפני שהמרקר נמשך
    requestAnimationFrame(function () {
      requestAnimationFrame(function () { blocks.forEach(function (b) { io.observe(b); }); });
    });
  }

  // מערכת ההפעלה
  var ua = navigator.userAgent || "";
  var plat = (navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || "";
  var os = null;
  if (/android|iphone|ipad|ipod/i.test(ua) || (/mac/i.test(plat) && navigator.maxTouchPoints > 1)) os = "mobile";
  else if (/win/i.test(plat) || /windows/i.test(ua)) os = "win";
  else if (/mac/i.test(plat) || /mac os x/i.test(ua)) os = "mac";
  else if (/linux|x11|cros/i.test(plat + " " + ua)) os = "linux";

  markMine();

  function markMine() {
    document.querySelectorAll("#files tr[data-os]").forEach(function (r) {
      if (r.getAttribute("data-os") !== os) return;
      r.classList.add("mine");
      var th = r.querySelector("th");
      if (th && !th.querySelector(".here")) {
        var s = document.createElement("span");
        s.className = "here";
        s.textContent = "המחשב הזה";
        th.appendChild(s);
      }
    });
  }

  // הגרסה האחרונה ומונה ההורדות, מ-GitHub. אם הבקשה נכשלת נשאר מה שכתוב בעמוד, בלי מונה.
  var API = "https://api.github.com/repos/motiml77/haraya-redesign/releases?per_page=100";
  var KEY = "ws-releases";
  var KINDS = [
    { re: /Setup.*\.exe$/i, os: "win", label: "חלונות 10 ו-11 (64 ביט)" },
    { re: /macOS-arm64\.dmg$/i, os: "mac", label: "מק, שבב Apple (M1 ומעלה)" },
    { re: /macOS-x86_64\.dmg$/i, os: "mac", label: "מק, אינטל" },
    { re: /linux-x86_64\.tar\.gz$/i, os: "linux", label: "לינוקס (x86-64)" }
  ];
  var nf = new Intl.NumberFormat("he-IL");

  function mb(bytes) { return (bytes / 1e6).toFixed(1) + "MB"; }
  function cell(tag, text) { var e = document.createElement(tag); if (text != null) e.textContent = text; return e; }

  function render(list) {
    var rels = list.filter(function (r) { return !r.draft && /^word-search-v/.test(r.tag_name); });
    if (!rels.length) return;
    rels.sort(function (a, b) { return a.published_at < b.published_at ? 1 : -1; });
    var last = rels[0], ver = last.tag_name.replace("word-search-v", "");
    var total = 0;
    rels.forEach(function (r) { r.assets.forEach(function (a) { total += a.download_count; }); });

    document.querySelectorAll("[data-ver]").forEach(function (e) { e.textContent = ver; });

    var assets = last.assets.slice().sort(function (a, b) { return kindIndex(a) - kindIndex(b); });
    var exe = assets.filter(function (a) { return KINDS[0].re.test(a.name); })[0];
    var btn = document.getElementById("dl-main");
    if (btn && exe) {
      btn.href = exe.browser_download_url;
      btn.querySelector(".size").textContent = mb(exe.size);
    }

    var table = document.getElementById("files");
    if (table && assets.length) {
      var head = table.querySelector("thead tr");
      if (head.children.length === 3) head.appendChild(cell("th", "הורדות")).setAttribute("scope", "col");
      var body = document.createElement("tbody");
      assets.forEach(function (a) {
        var k = KINDS[kindIndex(a)] || {};
        var tr = document.createElement("tr");
        if (k.os) tr.setAttribute("data-os", k.os);
        var th = cell("th", k.label || "קובץ נוסף"); th.setAttribute("scope", "row");
        var link = cell("a", a.name); link.href = a.browser_download_url;
        var td = cell("td"); td.appendChild(link);
        tr.appendChild(th); tr.appendChild(td);
        tr.appendChild(cell("td", mb(a.size)));
        var n = tr.appendChild(cell("td", nf.format(a.download_count)));
        n.className = "n";
        n.setAttribute("data-unit", a.download_count === 1 ? " הורדה" : " הורדות");
        body.appendChild(tr);
      });
      table.replaceChild(body, table.tBodies[0]);
      markMine();
    }

    var c = document.getElementById("dl-count");
    if (c && total > 0) {
      c.textContent = (total === 1 ? "הורד פעם אחת" : "הורד " + nf.format(total) + " פעמים") + " מאז הגרסה הראשונה";
      c.hidden = false;
    }
  }

  function kindIndex(a) {
    for (var i = 0; i < KINDS.length; i++) if (KINDS[i].re.test(a.name)) return i;
    return KINDS.length;
  }

  var cached = null;
  try { cached = JSON.parse(sessionStorage.getItem(KEY) || "null"); } catch (e) { cached = null; }
  if (cached && Date.now() - cached.t < 10 * 60 * 1000) {
    render(cached.d);
  } else if (window.fetch) {
    fetch(API, { headers: { Accept: "application/vnd.github+json" } })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (d) {
        try { sessionStorage.setItem(KEY, JSON.stringify({ t: Date.now(), d: d })); } catch (e) { /* פרטי */ }
        render(d);
      })
      .catch(function () { /* נשאר הטקסט הקבוע */ });
  }
})();
