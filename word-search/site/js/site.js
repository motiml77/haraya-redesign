// שני דברים בלבד: המרקר שנמשך מתחת למילים בדוגמה, והתאמת קישור ההורדה למחשב של הקורא.
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

  var rows = document.querySelectorAll("#files tr[data-os]");
  rows.forEach(function (r) {
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

  var btn = document.getElementById("dl-main");
  if (!btn || !os || os === "win") return;
  var other = btn.parentNode.querySelector(".quiet");
  var fine = document.querySelector(".daf-hero .fine");
  function pick(sel) { var a = document.querySelector(sel + " a"); return a ? a.href : null; }

  if (os === "mac") {
    btn.href = pick('#files tr[data-os="mac"]') || btn.href;
    btn.firstChild.nodeValue = "הורדה למק ";
    btn.querySelector(".size").textContent = "64.6MB";
    if (other) other.textContent = "מק אינטל, חלונות או לינוקס";
    if (fine) fine.innerHTML = 'גרסה 1.0.3 · למק עם שבב Apple (M1 ומעלה). למק עם מעבד אינטל יש <a href="#hora-a">קובץ נפרד</a>';
  } else if (os === "linux") {
    btn.href = pick('#files tr[data-os="linux"]') || btn.href;
    btn.firstChild.nodeValue = "הורדה ללינוקס ";
    btn.querySelector(".size").textContent = "153.9MB";
    if (other) other.textContent = "חלונות או מק";
    if (fine) fine.innerHTML = 'גרסה 1.0.3 · x86-64 · מחלצים ומריצים את <code>install.sh</code>';
  } else if (os === "mobile") {
    btn.href = "#hora-a";
    btn.firstChild.nodeValue = "קובצי ההורדה ";
    btn.querySelector(".size").textContent = "";
    if (other) other.remove();
    if (fine) fine.textContent = "התוכנה פועלת במחשב: חלונות, מק או לינוקס. אפשר לשלוח לעצמכם את הקישור ולהוריד מהמחשב.";
  }
})();
