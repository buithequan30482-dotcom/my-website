/* Bản đồ di tích – Google Maps (TR mục 6).
   - Có API key (Cấu hình hệ thống): Google Maps JavaScript API, đủ các điểm, cửa sổ thông tin, tuyến.
   - Chưa có key hoặc key lỗi: khung Google Maps nhúng (không cần key) + danh sách điểm; bấm điểm để xem trên Google Maps.
   Leaflet/OpenStreetMap chỉ còn là lựa chọn khi gọi rõ opts.engine = "osm". */
(function (w) {
  "use strict";
  var COLORS = { qgdb: "#A3302A", qg: "#B8893A", tinh: "#0E6B6B", kiemke: "#6F675B" };
  var BOUNDS = { south: 20.55, west: 106.95, north: 21.65, east: 108.15 };

  // Hình dạng biểu tượng khác nhau theo cấp: vuông, tròn, thoi, vuông viền
  function markerSVG(cap, label, size) {
    size = size || 26;
    var c = COLORS[cap] || "#6F675B", s = size, h = s / 2, shape;
    if (cap === "qgdb") shape = '<rect x="4" y="4" width="' + (s - 8) + '" height="' + (s - 8) + '" rx="2" fill="' + c + '" stroke="#fff" stroke-width="2.5"/>';
    else if (cap === "qg") shape = '<circle cx="' + h + '" cy="' + h + '" r="' + (h - 3) + '" fill="' + c + '" stroke="#fff" stroke-width="2.5"/>';
    else if (cap === "tinh") shape = '<rect x="' + (h - (s - 10) / 2) + '" y="' + (h - (s - 10) / 2) + '" width="' + (s - 10) + '" height="' + (s - 10) + '" fill="' + c + '" stroke="#fff" stroke-width="2.5" transform="rotate(45 ' + h + " " + h + ')"/>';
    else shape = '<rect x="5" y="5" width="' + (s - 10) + '" height="' + (s - 10) + '" fill="#fff" stroke="' + c + '" stroke-width="3.5"/>';
    var txt = label ? '<text x="' + h + '" y="' + (h + 4.5) + '" text-anchor="middle" font-family="sans-serif" font-weight="700" font-size="12" fill="' + (cap === "kiemke" ? c : "#fff") + '">' + label + "</text>" : "";
    return '<svg xmlns="http://www.w3.org/2000/svg" width="' + s + '" height="' + s + '" viewBox="0 0 ' + s + " " + s + '">' + shape + txt + "</svg>";
  }

  function esc(s) { return String(s || "").replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }

  function popupHTML(p, i18n) {
    return '<div class="map-pop">' + (p.img ? '<img src="' + esc(p.img) + '" alt="" referrerpolicy="no-referrer">' : "") +
      '<span class="seal seal-' + esc(p.cap) + '">' + esc(p.capLabel) + "</span>" +
      "<b>" + esc(p.site) + "</b>" + (p.name && p.name !== p.site ? '<div class="small muted">' + esc(p.name) + "</div>" : "") +
      '<a href="' + esc(p.url) + '">' + esc((i18n && i18n.view) || "Xem chi tiết") + "</a></div>";
  }

  function loadScript(src) {
    return new Promise(function (res, rej) {
      var s = document.createElement("script"); s.src = src; s.async = true; s.onload = res; s.onerror = rej;
      document.head.appendChild(s);
    });
  }
  function loadCSS(href) { var l = document.createElement("link"); l.rel = "stylesheet"; l.href = href; document.head.appendChild(l); }

  var googlePromise = null;
  function loadGoogle(key, lang) {
    if (googlePromise) return googlePromise;
    googlePromise = new Promise(function (res, rej) {
      var cb = "__vdGmapsReady";
      w[cb] = function () { res(w.google.maps); };
      var timer = setTimeout(function () { rej(new Error("timeout")); }, 8000);
      loadScript("https://maps.googleapis.com/maps/api/js?key=" + encodeURIComponent(key) + "&callback=" + cb +
        "&language=" + (lang === "zh-hans" ? "zh-CN" : lang) + "&region=VN&libraries=places")
        .then(function () { clearTimeout(timer); }).catch(function (e) { clearTimeout(timer); rej(e); });
      w.gm_authFailure = function () { rej(new Error("auth")); };
    });
    return googlePromise;
  }

  function leaflet(staticUrl) {
    if (w.L) return Promise.resolve(w.L);
    loadCSS(staticUrl + "vendor/leaflet/leaflet.css");
    loadCSS(staticUrl + "vendor/markercluster/MarkerCluster.css");
    loadCSS(staticUrl + "vendor/markercluster/MarkerCluster.Default.css");
    return loadScript(staticUrl + "vendor/leaflet/leaflet.js")
      .then(function () { return loadScript(staticUrl + "vendor/markercluster/leaflet.markercluster.js"); })
      .then(function () { return w.L; });
  }

  /* ---------- API chung ---------- */
  function VDMap(el, points, opts) {
    this.el = el; this.points = points || []; this.opts = opts || {};
    this.markers = [];
  }

  VDMap.prototype.init = function () {
    var self = this, o = this.opts;
    var fallback = function () { return o.engine === "osm" ? self._leaflet() : self._gembed(); };
    var p = o.key ? loadGoogle(o.key, o.lang).then(function (g) { self.engine = "google"; self._google(g); })
      .catch(fallback) : fallback();
    return p.then(function () { return self; });
  };

  VDMap.prototype._fitPoints = function () {
    return this.points.length ? this.points : [{ lat: 21.0, lng: 107.43 }];
  };

  VDMap.prototype._google = function (g) {
    var self = this, o = this.opts;
    this.map = new g.Map(this.el, {
      center: { lat: 21.0, lng: 107.43 }, zoom: 11, minZoom: 8, mapTypeControl: true, streetViewControl: false,
      restriction: { latLngBounds: BOUNDS, strictBounds: false }, gestureHandling: "cooperative",
      styles: [{ featureType: "poi.business", stylers: [{ visibility: "off" }] }],
    });
    var info = new g.InfoWindow();
    var bounds = new g.LatLngBounds();
    this.points.forEach(function (p, i) {
      var m = new g.Marker({
        position: { lat: p.lat, lng: p.lng }, map: self.map, title: p.site + (p.name !== p.site ? " – " + p.name : ""),
        icon: { url: "data:image/svg+xml;charset=UTF-8," + encodeURIComponent(markerSVG(p.cap, p.order ? String(p.order) : "", p.order ? 30 : 26)),
                anchor: new g.Point(p.order ? 15 : 13, p.order ? 15 : 13) },
      });
      m.addListener("click", function () { info.setContent(popupHTML(p, o.i18n)); info.open({ map: self.map, anchor: m }); });
      self.markers.push(m); bounds.extend(m.getPosition());
    });
    if (o.route && this.points.length > 1) {
      new g.Polyline({ map: this.map, path: this.points.map(function (p) { return { lat: p.lat, lng: p.lng }; }),
        strokeColor: "#A3302A", strokeOpacity: 0, icons: [{ icon: { path: "M 0,-1 0,1", strokeOpacity: .9, scale: 3 }, offset: "0", repeat: "14px" }] });
    }
    if (this.points.length > 1) this.map.fitBounds(bounds, 40);
    else if (this.points.length === 1) { this.map.setCenter(bounds.getCenter()); this.map.setZoom(o.zoom || 15); }
    this._info = info;
  };

  /* ---------- Google Maps nhúng không cần API key ---------- */
  function gUrl(p, lang, zoom, sat) {
    // Dạng nhúng Google Maps không cần API key (maps.google.com/maps?...&output=embed) – cần tham số q để hiển thị.
    var hl = lang === "zh-hans" ? "zh-CN" : (lang || "vi");
    var base = "https://maps.google.com/maps?hl=" + hl + "&output=embed&t=" + (sat ? "k" : "m");
    if (!p) return base + "&q=" + encodeURIComponent("Vân Đồn, Quảng Ninh") + "&z=11";
    return base + "&q=" + p.lat.toFixed(6) + "," + p.lng.toFixed(6) + "&z=" + (zoom || 16);
  }

  VDMap.prototype._gembed = function () {
    var self = this, o = this.opts, el = this.el, pts = this.points, i18n = o.i18n || {};
    self.engine = "gembed";
    el.classList.add("gmap-lite");
    el.innerHTML = "";
    var withList = (o.cluster || o.route) && pts.length > 1;
    var frameWrap = document.createElement("div");
    frameWrap.className = "gmap-frame";
    var iframe = document.createElement("iframe");
    iframe.referrerPolicy = "no-referrer-when-downgrade";
    iframe.title = i18n.mapTitle || "Google Maps";
    iframe.setAttribute("allowfullscreen", "");
    frameWrap.appendChild(iframe);
    var bar = document.createElement("div");
    bar.className = "gmap-bar";
    var label = document.createElement("span");
    var sat = false, cur = null;
    var satBtn = document.createElement("button");
    satBtn.type = "button"; satBtn.textContent = i18n.satellite || "Vệ tinh";
    var open = document.createElement("a");
    open.target = "_blank"; open.rel = "noopener"; open.textContent = i18n.openGoogle || "Mở Google Maps";
    bar.appendChild(label); bar.appendChild(satBtn); bar.appendChild(open);
    frameWrap.appendChild(bar);
    var listEl = null, buttons = [];
    function show(i, zoom) {
      cur = i;
      var p = i == null ? null : pts[i];
      iframe.src = gUrl(p, o.lang, zoom || o.zoom, sat);
      label.textContent = p ? p.site + (p.name && p.name !== p.site ? " – " + p.name : "") : (i18n.overview || "Vân Đồn");
      open.href = p ? "https://www.google.com/maps/search/?api=1&query=" + p.lat + "," + p.lng : "https://www.google.com/maps/@20.98,107.43,11z";
      buttons.forEach(function (b, k) { b.setAttribute("aria-current", k === i ? "true" : "false"); });
    }
    satBtn.addEventListener("click", function () {
      sat = !sat; satBtn.textContent = sat ? (i18n.roadmap || "Bản đồ") : (i18n.satellite || "Vệ tinh"); show(cur);
    });
    if (withList) {
      listEl = document.createElement("ol");
      listEl.className = "gmap-list" + (o.route ? " is-route" : "");
      pts.forEach(function (p, i) {
        var li = document.createElement("li");
        var b = document.createElement("button");
        b.type = "button";
        var sub = !o.route && i > 0 && pts[i - 1].site === p.site;
        if (sub) { li.className = "is-sub"; b.innerHTML = "<span><small>" + esc(p.name) + "</small></span>"; }
        else b.innerHTML = '<span class="seal seal-' + esc(p.cap) + '"></span><span><b>' + esc(p.site) + "</b>" +
          (p.name && p.name !== p.site ? "<small>" + esc(p.name) + "</small>" : "") + "</span>";
        b.addEventListener("click", function () { show(i); });
        li.appendChild(b);
        if (!sub) {
          var a = document.createElement("a");
          a.href = p.url; a.textContent = i18n.view || "Xem chi tiết"; a.className = "gmap-more";
          li.appendChild(a);
        }
        listEl.appendChild(li); buttons.push(b);
      });
      el.appendChild(listEl);
    }
    el.appendChild(frameWrap);
    show(pts.length === 1 || o.route || !withList ? (pts.length ? 0 : null) : null, pts.length === 1 ? o.zoom : null);
    return Promise.resolve();
  };

  VDMap.prototype._leaflet = function () {
    var self = this, o = this.opts;
    return leaflet(o.staticUrl || "/static/").then(function (L) {
      self.engine = "leaflet";
      self.map = L.map(self.el, { scrollWheelZoom: false, minZoom: 8,
        maxBounds: [[BOUNDS.south, BOUNDS.west], [BOUNDS.north, BOUNDS.east]] }).setView([21.0, 107.43], 11);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 18, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' }).addTo(self.map);
      var group = o.cluster && L.markerClusterGroup ? L.markerClusterGroup({ maxClusterRadius: 36 }) : L.featureGroup();
      self.points.forEach(function (p) {
        var s = p.order ? 30 : 26;
        var icon = L.divIcon({ html: markerSVG(p.cap, p.order ? String(p.order) : "", s), className: "vd-mk", iconSize: [s, s], iconAnchor: [s / 2, s / 2] });
        var m = L.marker([p.lat, p.lng], { icon: icon, title: p.site, keyboard: true }).bindPopup(popupHTML(p, o.i18n));
        group.addLayer(m); self.markers.push(m);
      });
      group.addTo(self.map);
      if (o.route && self.points.length > 1) {
        L.polyline(self.points.map(function (p) { return [p.lat, p.lng]; }), { color: "#A3302A", weight: 2.5, dashArray: "4 8" }).addTo(self.map);
      }
      if (self.points.length > 1) self.map.fitBounds(L.latLngBounds(self.points.map(function (p) { return [p.lat, p.lng]; })).pad(0.12));
      else if (self.points.length === 1) self.map.setView([self.points[0].lat, self.points[0].lng], o.zoom || 15);
      self.map.on("focus", function () { self.map.scrollWheelZoom.enable(); });
      self.map.on("blur", function () { self.map.scrollWheelZoom.disable(); });
    });
  };

  VDMap.prototype.focus = function (i) {
    if (this.engine === "gembed") {
      var b = this.el.querySelectorAll(".gmap-list button")[i];
      if (b) b.click(); else { this._gembedShow = true; this.el.querySelector("iframe").src = gUrl(this.points[i], this.opts.lang, 17); }
      var lab = this.el.querySelector(".gmap-bar span"), p0 = this.points[i];
      if (lab && p0) lab.textContent = p0.site + (p0.name && p0.name !== p0.site ? " – " + p0.name : "");
      this.el.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    var m = this.markers[i], p = this.points[i];
    if (!m) return;
    if (this.engine === "google") { this.map.panTo({ lat: p.lat, lng: p.lng }); this.map.setZoom(16); w.google.maps.event.trigger(m, "click"); }
    else { this.map.setView([p.lat, p.lng], 16); m.openPopup(); }
    this.el.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  VDMap.prototype.locate = function () {
    var self = this;
    if (self.engine === "gembed") { window.open("https://www.google.com/maps/@?api=1&map_action=map", "_blank", "noopener"); return; }
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(function (pos) {
      var ll = [pos.coords.latitude, pos.coords.longitude];
      if (self.engine === "google") {
        new w.google.maps.Marker({ position: { lat: ll[0], lng: ll[1] }, map: self.map, title: "📍" });
        self.map.panTo({ lat: ll[0], lng: ll[1] });
      } else {
        w.L.circleMarker(ll, { radius: 8, color: "#fff", weight: 3, fillColor: "#1d6fd8", fillOpacity: 1 }).addTo(self.map);
        self.map.setView(ll, 13);
      }
    });
  };

  w.VDMap = VDMap;
  w.VDMap.markerSVG = markerSVG;

  // Khởi tạo tự động cho phần tử có data-map
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-map]").forEach(function (el) {
      var src = document.getElementById(el.getAttribute("data-map"));
      var pts = src ? JSON.parse(src.textContent) : [];
      var m = new VDMap(el, pts, {
        key: el.getAttribute("data-key") || "", lang: document.documentElement.lang || "vi",
        staticUrl: el.getAttribute("data-static") || "/static/", cluster: el.hasAttribute("data-cluster"),
        route: el.hasAttribute("data-route"), zoom: +el.getAttribute("data-zoom") || 15, i18n: w.VD_I18N || {},
      });
      m.init().then(function () {
        el.vdmap = m;
        document.querySelectorAll('[data-focus-map="' + el.id + '"]').forEach(function (b) {
          b.addEventListener("click", function () { m.focus(+b.getAttribute("data-index")); });
        });
        var loc = document.querySelector('[data-locate="' + el.id + '"]');
        if (loc) loc.addEventListener("click", function () { m.locate(); });
      });
    });
  });
})(window);
