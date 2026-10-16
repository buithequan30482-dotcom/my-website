/* Hải đồ trang chủ: vẽ các điểm di tích theo tọa độ thật trên lưới kinh vĩ độ (SVG, không cần dịch vụ bản đồ). */
(function () {
  "use strict";
  var el = document.getElementById("hai-do");
  if (!el) return;
  var pts = JSON.parse(document.getElementById(el.getAttribute("data-points")).textContent);
  if (!pts.length) return;
  var NS = "http://www.w3.org/2000/svg";
  var W = 700, H = 600, PAD = 46;
  var lats = pts.map(function (p) { return p.lat; }), lngs = pts.map(function (p) { return p.lng; });
  var s = Math.min.apply(null, lats) - 0.025, n = Math.max.apply(null, lats) + 0.025;
  var we = Math.min.apply(null, lngs) - 0.03, e = Math.max.apply(null, lngs) + 0.03;
  var k = Math.cos((s + n) / 2 * Math.PI / 180);
  var sx = (W - 2 * PAD) / ((e - we) * k), sy = (H - 2 * PAD) / (n - s), sc = Math.min(sx, sy);
  var ox = (W - (e - we) * k * sc) / 2, oy = (H - (n - s) * sc) / 2;
  var X = function (lng) { return ox + (lng - we) * k * sc; };
  var Y = function (lat) { return H - oy - (lat - s) * sc; };
  var svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "0 0 " + W + " " + H);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", el.getAttribute("data-label") || "");
  function mk(tag, attrs, parent) {
    var x = document.createElementNS(NS, tag);
    for (var a in attrs) x.setAttribute(a, attrs[a]);
    (parent || svg).appendChild(x);
    return x;
  }
  function dm(v) { var d = Math.floor(v), m = Math.round((v - d) * 60); if (m === 60) { d++; m = 0; } return d + "°" + (m < 10 ? "0" : "") + m + "′"; }
  // Lưới kinh vĩ độ, bước 6′
  var step = 0.1;
  for (var la = Math.ceil(s / step) * step; la <= n; la += step) {
    mk("line", { x1: 0, x2: W, y1: Y(la), y2: Y(la), class: "grat" });
    mk("text", { x: 4, y: Y(la) - 5, class: "grat-label" }).textContent = dm(la) + "N";
  }
  for (var lo = Math.ceil(we / step) * step; lo <= e; lo += step) {
    mk("line", { y1: 0, y2: H, x1: X(lo), x2: X(lo), class: "grat" });
    mk("text", { x: X(lo) + 5, y: H - 6, class: "grat-label" }).textContent = dm(lo) + "E";
  }
  // Hoa la bàn
  var cg = mk("g", { class: "compass", transform: "translate(" + (W - 54) + ",58)" });
  mk("circle", { r: 26, "stroke-width": 1 }, cg); mk("circle", { r: 18, "stroke-width": .6 }, cg);
  mk("path", { d: "M0,-34 L5,0 L0,34 L-5,0 Z", fill: "#B8893A", stroke: "none", opacity: .85 }, cg);
  mk("path", { d: "M-34,0 L0,4 L34,0 L0,-4 Z", fill: "#B8893A", stroke: "none", opacity: .45 }, cg);
  mk("text", { y: -40, "text-anchor": "middle", class: "grat-label", stroke: "none" }, cg).textContent = "N";
  // Nhãn đảo tại trọng tâm các điểm cùng đảo
  var groups = {};
  pts.forEach(function (p) { if (p.dao) { (groups[p.dao] = groups[p.dao] || []).push(p); } });
  var centers = {};
  Object.keys(groups).forEach(function (g) {
    var a = groups[g], cx = 0, cy = 0;
    a.forEach(function (p) { cx += X(p.lng); cy += Y(p.lat); });
    centers[g] = [cx / a.length, cy / a.length];
  });
  // Tuyến ra đảo (minh họa): từ trung tâm Cái Bầu tới các đảo
  var hub = centers[el.getAttribute("data-hub")];
  if (hub) Object.keys(centers).forEach(function (g) {
    if (centers[g] === hub) return;
    var c = centers[g], mx = (hub[0] + c[0]) / 2 + (c[1] - hub[1]) * 0.15, my = (hub[1] + c[1]) / 2 - (c[0] - hub[0]) * 0.15;
    mk("path", { d: "M" + hub[0] + "," + hub[1] + " Q" + mx + "," + my + " " + c[0] + "," + c[1], class: "route" });
  });
  Object.keys(centers).forEach(function (g) {
    var c = centers[g];
    mk("text", { x: c[0] + 16, y: c[1] + 26, class: "island" }).textContent = groups[g][0].daoLabel || g;
  });
  // Điểm di tích
  var tip = document.createElement("div"); tip.className = "chart-tip"; el.appendChild(tip);
  var order = { kiemke: 0, tinh: 1, qg: 2, qgdb: 3 };
  pts.slice().sort(function (a, b) { return order[a.cap] - order[b.cap]; }).forEach(function (p) {
    var x = X(p.lng), y = Y(p.lat), r = p.cap === "qgdb" ? 8 : p.cap === "qg" ? 7 : 6;
    var a = mk("a", { href: p.url, class: "pt", "aria-label": p.site + " – " + p.capLabel });
    var c = { qgdb: "#A3302A", qg: "#B8893A", tinh: "#0E6B6B", kiemke: "#6F675B" }[p.cap];
    if (p.cap === "qgdb") mk("rect", { x: x - r, y: y - r, width: 2 * r, height: 2 * r, fill: c, class: "mk" }, a);
    else if (p.cap === "qg") mk("circle", { cx: x, cy: y, r: r, fill: c, class: "mk" }, a);
    else if (p.cap === "tinh") mk("rect", { x: x - r * .8, y: y - r * .8, width: r * 1.6, height: r * 1.6, fill: c, class: "mk", transform: "rotate(45 " + x + " " + y + ")" }, a);
    else mk("rect", { x: x - 4.5, y: y - 4.5, width: 9, height: 9, fill: "#F6F0E4", stroke: c, "stroke-width": 2.2, class: "mk" }, a);
    var showTip = function () {
      var b = el.getBoundingClientRect(), sb = svg.getBoundingClientRect();
      tip.textContent = p.site + (p.name !== p.site ? " · " + p.name : "");
      tip.style.left = (x / W * sb.width + sb.left - b.left) + "px";
      tip.style.top = (y / H * sb.height + sb.top - b.top) + "px";
      tip.classList.add("on");
    };
    a.addEventListener("mouseenter", showTip); a.addEventListener("focus", showTip);
    a.addEventListener("mouseleave", function () { tip.classList.remove("on"); });
    a.addEventListener("blur", function () { tip.classList.remove("on"); });
  });
  el.insertBefore(svg, el.firstChild);
})();
