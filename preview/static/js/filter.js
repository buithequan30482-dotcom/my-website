/* Bộ lọc di tích chạy ngay trên trình duyệt (trang Danh sách và Bản đồ).
   - Danh sách: máy chủ gửi đủ mọi di tích (mỗi thẻ mang data-cap/loai/khu/tq/s); tích ô nào là lọc ngay, không tải lại.
   - Bản đồ: JSON điểm chứa đủ mọi di tích; lọc trước khi map.js khởi tạo, đổi bộ lọc thì mở lại trang với tham số mới.
   - Tham số lọc luôn được ghi lên địa chỉ (?cap=qg&khu=…) để chia sẻ, quay lại, và để chạy được cả trên bản xem trước
     tĩnh (GitHub Pages) – nơi máy chủ không đọc được tham số. Phải nạp TRƯỚC map.js. */
(function () {
  "use strict";
  var form = document.getElementById("filters");
  if (!form) return;
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var grid = document.querySelector("[data-results]");
  var mapSrc = document.getElementById("pts-map") || document.getElementById("pts-list");
  var sortForm = document.querySelector("[data-sort-form]");
  var sortSel = document.getElementById("sort");
  var countEl = document.querySelector("[data-count]");
  var toggle = document.querySelector(".filter-toggle");
  var doneBtn = form.querySelector("[data-done]");
  var KEYS = ["q", "cap", "loai", "khu", "tq", "sort"];

  form.setAttribute("data-live", "");
  if (sortForm) sortForm.setAttribute("data-live", "");

  function norm(s) {
    s = String(s || "").replace(/đ/g, "d").replace(/Đ/g, "D");
    if (s.normalize) s = s.normalize("NFD").replace(/[̀-ͯ]/g, "");
    return s.toLowerCase().replace(/\s+/g, " ").trim();
  }

  // 1) Đưa tham số trên địa chỉ vào form (bản tĩnh: HTML luôn là trạng thái "không lọc")
  var url = new URLSearchParams(location.search);
  var hasUrlFilter = KEYS.some(function (k) { return url.has(k); });
  if (hasUrlFilter) {
    ["cap", "loai", "khu", "tq"].forEach(function (name) {
      var vals = url.getAll(name);
      $$('input[name="' + name + '"]', form).forEach(function (cb) { cb.checked = vals.indexOf(cb.value) >= 0; });
    });
    if (form.q) form.q.value = url.get("q") || "";
    if (sortSel && url.get("sort")) sortSel.value = url.get("sort");
  }

  function state() {
    var st = { q: norm(form.q ? form.q.value : ""), cap: [], loai: [], khu: [], tq: false };
    ["cap", "loai", "khu"].forEach(function (n) {
      st[n] = $$('input[name="' + n + '"]:checked', form).map(function (c) { return c.value; });
    });
    var tq = form.querySelector('input[name="tq"]');
    st.tq = !!(tq && tq.checked);
    return st;
  }

  function match(it, st) {
    if (st.cap.length && st.cap.indexOf(it.cap) < 0) return false;
    if (st.loai.length && !it.loai.some(function (x) { return st.loai.indexOf(x) >= 0; })) return false;
    if (st.khu.length && !it.khu.some(function (x) { return st.khu.indexOf(x) >= 0; })) return false;
    if (st.tq && !it.tq) return false;
    if (st.q && it.s.indexOf(st.q) < 0) return false;
    return true;
  }

  function query() {
    var p = new URLSearchParams();
    var q = form.q ? form.q.value.trim() : "";
    if (q) p.set("q", q);
    $$("input[type=checkbox]:checked", form).forEach(function (c) { p.append(c.name, c.value); });
    if (sortSel && sortSel.value && sortSel.value !== "noibat" && sortSel.value !== "gan") p.set("sort", sortSel.value);
    return p.toString();
  }

  function setDone(n) { if (doneBtn) doneBtn.textContent = doneBtn.getAttribute("data-label").replace("__N__", n); }

  function setCount(n) {
    if (!countEl) return;
    countEl.textContent = n === 1 ? countEl.getAttribute("data-one") : countEl.getAttribute("data-many").replace("__N__", n);
  }

  function updateBadge(st) {
    var n = st.cap.length + st.loai.length + st.khu.length + (st.tq ? 1 : 0) + (st.q ? 1 : 0);
    if (toggle) {
      if (!toggle.getAttribute("data-label")) toggle.setAttribute("data-label", toggle.textContent.trim());
      toggle.textContent = toggle.getAttribute("data-label") + (n ? " (" + n + ")" : "");
    }
  }

  function syncLinks(qs) {
    $$("a[data-keepqs]").forEach(function (a) { a.href = a.href.split("?")[0] + (qs ? "?" + qs : ""); });
    try { history.replaceState(null, "", location.pathname + (qs ? "?" + qs : "") + location.hash); } catch (e) { /* bỏ qua */ }
  }

  // 2) Trang danh sách
  var items = grid ? $$(".site-item", grid).map(function (el) {
    return {
      el: el, cap: el.getAttribute("data-cap"), loai: (el.getAttribute("data-loai") || "").split(" ").filter(Boolean),
      khu: (el.getAttribute("data-khu") || "").split(" ").filter(Boolean), tq: el.getAttribute("data-tq") === "1",
      s: el.getAttribute("data-s") || "", order: +el.getAttribute("data-thu-tu") || 0,
      name: norm((el.querySelector("h3") || el).textContent), rating: parseFloat(el.getAttribute("data-rating")) || 0,
      nrating: +el.getAttribute("data-nrating") || 0,
      lat: parseFloat(el.getAttribute("data-lat")), lng: parseFloat(el.getAttribute("data-lng")), dist: null,
    };
  }) : [];

  function sortItems(mode) {
    var cmp = {
      az: function (a, b) { return a.name < b.name ? -1 : a.name > b.name ? 1 : 0; },
      danhgia: function (a, b) { return (b.rating - a.rating) || (b.nrating - a.nrating) || (a.order - b.order); },
      gan: function (a, b) { return (a.dist == null ? 1e9 : a.dist) - (b.dist == null ? 1e9 : b.dist); },
    }[mode] || function (a, b) { return a.order - b.order; };
    items.slice().sort(cmp).forEach(function (it) { grid.appendChild(it.el); });
  }

  function hav(la1, lo1, la2, lo2) {
    var r = Math.PI / 180, dla = (la2 - la1) * r, dlo = (lo2 - lo1) * r;
    var a = Math.sin(dla / 2) * Math.sin(dla / 2) + Math.cos(la1 * r) * Math.cos(la2 * r) * Math.sin(dlo / 2) * Math.sin(dlo / 2);
    return 12742 * Math.asin(Math.sqrt(a));
  }

  function applyList() {
    var st = state(), n = 0;
    items.forEach(function (it) { var ok = match(it, st); it.el.hidden = !ok; if (ok) n++; });
    var empty = document.querySelector("[data-empty]");
    if (empty) empty.hidden = n > 0;
    setCount(n); updateBadge(st); syncLinks(query());
    setDone(n);
    return n;
  }

  // 3) Trang bản đồ: lọc JSON trước khi map.js đọc
  function applyMap() {
    var st = state(), all;
    try { all = JSON.parse(mapSrc.textContent); } catch (e) { return; }
    var pts = all.filter(function (p) { return match({ cap: p.cap, loai: p.loai || [], khu: p.khu || [], tq: p.tq !== false, s: p.s || "" }, st); });
    mapSrc.textContent = JSON.stringify(pts);
    var sites = {};
    pts.forEach(function (p) { sites[p.ma] = 1; });
    var n = Object.keys(sites).length;
    setCount(n); setDone(n); updateBadge(st); syncLinks(query());
  }

  if (doneBtn) {
    if (!doneBtn.getAttribute("data-label")) doneBtn.setAttribute("data-label", "__N__");
    doneBtn.hidden = false;
    doneBtn.addEventListener("click", function () {
      form.classList.remove("open");
      if (toggle) toggle.setAttribute("aria-expanded", "false");
      var r = document.getElementById("results");
      if (r) r.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  if (grid) {
    form.addEventListener("change", function (e) { if (e.target.matches("input[type=checkbox]")) applyList(); });
    var timer;
    if (form.q) form.q.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(applyList, 150); });
    form.addEventListener("submit", function (e) { e.preventDefault(); applyList(); });
    if (sortSel) {
      sortSel.addEventListener("change", function () {
        if (sortSel.value !== "gan") { sortItems(sortSel.value); applyList(); return; }
        if (!navigator.geolocation) return;
        navigator.geolocation.getCurrentPosition(function (pos) {
          items.forEach(function (it) { it.dist = isNaN(it.lat) ? null : hav(pos.coords.latitude, pos.coords.longitude, it.lat, it.lng); });
          sortItems("gan");
        }, function () { alert((window.VD_I18N && window.VD_I18N.geoFail) || "Không lấy được vị trí. Hãy cho phép trình duyệt truy cập vị trí."); });
      });
      if (sortForm) sortForm.addEventListener("submit", function (e) { e.preventDefault(); });
    }
    $$("[data-clear]").forEach(function (a) {
      a.addEventListener("click", function (e) {
        e.preventDefault();
        $$("input[type=checkbox]", form).forEach(function (c) { c.checked = false; });
        if (form.q) form.q.value = "";
        applyList();
      });
    });
    if (hasUrlFilter && sortSel) sortItems(sortSel.value);
    applyList();
  } else if (mapSrc) {
    applyMap();
    var go = function () { var qs = query(); location.href = location.pathname + (qs ? "?" + qs : ""); };
    form.addEventListener("change", function (e) { if (e.target.matches("input[type=checkbox]")) go(); });
    form.addEventListener("submit", function (e) { e.preventDefault(); go(); });
  }
})();
