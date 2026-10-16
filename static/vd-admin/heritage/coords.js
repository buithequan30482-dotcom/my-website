/* Thẻ "Vị trí": nhập tọa độ 3 cách, đồng bộ hai chiều (TR FR-A04, bài hướng dẫn "toa-do").
 * (1) Dán DMS 20°53'49.3"N 107°18'33.7"E  (2) thập phân 20.897, 107.309  (3) bấm / kéo điểm trên bản đồ.
 * Google Maps JS (có khóa trong Cấu hình hệ thống, thêm libraries=places) hoặc Leaflet + OSM / Esri vệ tinh + Nominatim.
 */
(function () {
  "use strict";
  var VDH = window.VDH = window.VDH || {};
  var cfg = null;
  var gmapsPromise = null;

  /* ---------------------------------------------------------- Đọc tọa độ (giống core.utils.parse_coordinates) */
  var DMS_RE = /(\d{1,3})\s*[°º]\s*(\d{1,2})\s*['’′]\s*(\d{1,2}(?:[.,]\d+)?)\s*["”″]?\s*([NSns])[\s,;]*(\d{1,3})\s*[°º]\s*(\d{1,2})\s*['’′]\s*(\d{1,2}(?:[.,]\d+)?)\s*["”″]?\s*([EWew])/;
  var DEC_RE = /^\s*(-?\d{1,3}(?:[.,]\d+)?)\s*[,;\s]\s*(-?\d{1,3}(?:[.,]\d+)?)\s*$/;
  function dms(d, m, s, h) {
    d = parseFloat(d); m = parseFloat(m); s = parseFloat(String(s).replace(",", "."));
    var note = "";
    if (s >= 60) { s -= 60; m += 1; note = "Đã chuẩn hóa giây ≥ 60"; }
    if (m >= 60) { m -= 60; d += 1; }
    var v = d + m / 60 + s / 3600;
    if (/[SWsw]/.test(h)) v = -v;
    return [v, note];
  }
  VDH.parseCoord = function (text) {
    var t = String(text || "").trim();
    if (!t) return { error: "Chưa nhập tọa độ." };
    var m = t.match(DMS_RE), lat, lng, note = "";
    if (m) {
      var a = dms(m[1], m[2], m[3], m[4]), b = dms(m[5], m[6], m[7], m[8]);
      lat = a[0]; lng = b[0]; note = a[1] || b[1];
    } else {
      m = t.match(DEC_RE);
      if (!m) return { error: "Không đọc được tọa độ. Ví dụ hợp lệ: 20°53'49.3\"N 107°18'33.7\"E hoặc 20.897028, 107.309361" };
      lat = parseFloat(m[1].replace(",", ".")); lng = parseFloat(m[2].replace(",", "."));
    }
    if (!(lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180)) return { error: "Tọa độ vượt giới hạn hợp lệ." };
    return { lat: Math.round(lat * 1e6) / 1e6, lng: Math.round(lng * 1e6) / 1e6, note: note };
  };
  function inVanDon(lat, lng) {
    var b = cfg.bounds;
    return lat >= b.south && lat <= b.north && lng >= b.west && lng <= b.east;
  }
  function fmt(v) { return (Math.round(v * 1e6) / 1e6).toFixed(6); }

  /* ---------------------------------------------------------- Bản đồ: Google hoặc Leaflet */
  function loadGoogle() {
    if (gmapsPromise) return gmapsPromise;
    gmapsPromise = new Promise(function (resolve, reject) {
      if (window.google && window.google.maps) return resolve();
      var cb = "vdhGmapsReady" + Date.now();
      window[cb] = function () { resolve(); };
      var s = document.createElement("script");
      s.src = "https://maps.googleapis.com/maps/api/js?key=" + encodeURIComponent(cfg.key) +
        "&libraries=places&language=vi&region=VN&loading=async&callback=" + cb;
      s.async = true;
      s.onerror = function () { reject(new Error("gmaps")); };
      document.head.appendChild(s);
      setTimeout(function () { if (!(window.google && window.google.maps)) reject(new Error("timeout")); }, 12000);
    });
    return gmapsPromise;
  }

  function LeafletMap(el, onPick) {
    var map = L.map(el, { scrollWheelZoom: false, zoomControl: true });
    var osm = L.tileLayer(cfg.osm, { maxZoom: 19, subdomains: "abc", attribution: "© OpenStreetMap" });
    var sat = L.tileLayer(cfg.esri, { maxZoom: 19, attribution: "Ảnh vệ tinh © Esri, Maxar, Earthstar Geographics" });
    osm.addTo(map);
    var b = cfg.bounds;
    map.fitBounds([[b.south, b.west], [b.north, b.east]]);
    var bounds = L.rectangle([[b.south, b.west], [b.north, b.east]], { color: "#0E6B6B", weight: 1, fill: false, dashArray: "4 4", interactive: false });
    bounds.addTo(map);
    var marker = null;
    map.on("click", function (e) { onPick(e.latlng.lat, e.latlng.lng, "map"); });
    map.on("focus", function () { map.scrollWheelZoom.enable(); });
    map.on("blur", function () { map.scrollWheelZoom.disable(); });
    var satOn = false;
    return {
      setMarker: function (lat, lng, pan) {
        if (lat == null) { if (marker) { map.removeLayer(marker); marker = null; } return; }
        if (!marker) {
          marker = L.marker([lat, lng], { draggable: true, autoPan: true, title: "Kéo để chỉnh vị trí" }).addTo(map);
          marker.on("dragend", function () { var p = marker.getLatLng(); onPick(p.lat, p.lng, "drag"); });
        } else marker.setLatLng([lat, lng]);
        if (pan) map.setView([lat, lng], Math.max(map.getZoom(), 16));
      },
      goTo: function (lat, lng, zoom) { map.setView([lat, lng], zoom || 17); },
      toggleSat: function () {
        satOn = !satOn;
        if (satOn) { map.removeLayer(osm); sat.addTo(map); } else { map.removeLayer(sat); osm.addTo(map); }
        return satOn;
      },
      resize: function () { map.invalidateSize(); },
      kind: "leaflet"
    };
  }

  function GoogleMap(el, onPick) {
    var g = window.google.maps;
    var b = cfg.bounds;
    var map = new g.Map(el, { center: { lat: cfg.center[0], lng: cfg.center[1] }, zoom: 10, mapTypeId: "roadmap",
      streetViewControl: false, fullscreenControl: true, mapTypeControl: false, gestureHandling: "cooperative" });
    map.fitBounds({ south: b.south, west: b.west, north: b.north, east: b.east });
    new g.Rectangle({ map: map, bounds: { south: b.south, west: b.west, north: b.north, east: b.east },
      strokeColor: "#0E6B6B", strokeWeight: 1, fillOpacity: 0, clickable: false });
    var marker = null;
    map.addListener("click", function (e) { onPick(e.latLng.lat(), e.latLng.lng(), "map"); });
    var satOn = false;
    return {
      map: map,
      setMarker: function (lat, lng, pan) {
        if (lat == null) { if (marker) { marker.setMap(null); marker = null; } return; }
        if (!marker) {
          marker = new g.Marker({ map: map, position: { lat: lat, lng: lng }, draggable: true, title: "Kéo để chỉnh vị trí" });
          marker.addListener("dragend", function (e) { onPick(e.latLng.lat(), e.latLng.lng(), "drag"); });
        } else marker.setPosition({ lat: lat, lng: lng });
        if (pan) { map.setCenter({ lat: lat, lng: lng }); if (map.getZoom() < 16) map.setZoom(16); }
      },
      goTo: function (lat, lng, zoom) { map.setCenter({ lat: lat, lng: lng }); map.setZoom(zoom || 17); },
      toggleSat: function () { satOn = !satOn; map.setMapTypeId(satOn ? "hybrid" : "roadmap"); return satOn; },
      resize: function () { /* Google tự xử lý */ },
      kind: "google"
    };
  }

  /* ---------------------------------------------------------- Mỗi điểm */
  function initPoint(row) {
    if (row._vdhPoint || row.classList.contains("empty-form")) return;
    var text = row.querySelector("input.vdh-coord-text");
    var lat = row.querySelector("input.vdh-lat");
    var lng = row.querySelector("input.vdh-lng");
    var mapEl = row.querySelector(".vdh-map");
    var msg = row.querySelector(".vdh-coord-msg");
    var state = row.querySelector(".vdh-point-state");
    var parseBtn = row.querySelector(".vdh-parse");
    var satBtn = row.querySelector(".vdh-sat");
    var q = row.querySelector(".vdh-map-q");
    var go = row.querySelector(".vdh-map-go");
    var results = row.querySelector(".vdh-map-results");
    var nameInp = row.querySelector("input[name$='-ten_vi']");
    if (!text || !lat || !lng || !mapEl) return;
    var api = null;
    var self = row._vdhPoint = {};

    function say(m, level) {
      msg.textContent = m || "";
      msg.className = "vdh-coord-msg" + (level ? " is-" + level : "");
    }
    function current() {
      var a = parseFloat(String(lat.value).replace(",", ".")), b = parseFloat(String(lng.value).replace(",", "."));
      return isNaN(a) || isNaN(b) ? null : [a, b];
    }
    function check(note) {
      var c = current();
      if (!c) { state.textContent = "chưa có tọa độ"; state.className = "vdh-point-state is-miss"; return; }
      state.textContent = fmt(c[0]) + ", " + fmt(c[1]);
      state.className = "vdh-point-state is-ok";
      if (!inVanDon(c[0], c[1])) {
        say("⚠ Tọa độ nằm ngoài phạm vi Vân Đồn (khung nét đứt trên bản đồ). Kiểm tra lại – có thể nhầm vĩ độ / kinh độ.", "warn");
        state.className = "vdh-point-state is-warn";
      } else {
        say((note ? note + ". " : "") + "Vĩ độ " + fmt(c[0]) + ", kinh độ " + fmt(c[1]) + " – trong phạm vi Vân Đồn.", "ok");
      }
    }
    function setAll(a, b, source, note) {
      lat.value = fmt(a); lng.value = fmt(b);
      if (source !== "text") text.value = fmt(a) + ", " + fmt(b);
      if (api) api.setMarker(a, b, source !== "map" && source !== "drag");
      check(note);
      row.dispatchEvent(new Event("change", { bubbles: true }));
    }
    function readText() {
      var r = VDH.parseCoord(text.value);
      if (r.error) { say(r.error, "error"); text.setAttribute("aria-invalid", "true"); return; }
      text.removeAttribute("aria-invalid");
      setAll(r.lat, r.lng, "text", r.note);
    }
    parseBtn.addEventListener("click", readText);
    text.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); readText(); } });
    text.addEventListener("paste", function () { setTimeout(readText, 0); });
    text.addEventListener("change", function () { if (text.value.trim()) readText(); else { lat.value = ""; lng.value = ""; if (api) api.setMarker(null); check(); } });
    function fromNumbers() {
      var c = current();
      if (c) { text.value = fmt(c[0]) + ", " + fmt(c[1]); if (api) api.setMarker(c[0], c[1], true); check(); }
      else if (!lat.value && !lng.value) { text.value = ""; if (api) api.setMarker(null); check(); }
    }
    lat.addEventListener("change", fromNumbers);
    lng.addEventListener("change", fromNumbers);
    // Nhập "20.89, 107.3" vào ô vĩ độ: tự tách.
    lat.addEventListener("paste", function (e) {
      var t = (e.clipboardData || window.clipboardData).getData("text");
      if (/[,;\s]/.test(t.trim())) { e.preventDefault(); text.value = t; readText(); }
    });

    function pick(a, b, source) { setAll(a, b, source); say((source === "drag" ? "Đã chỉnh điểm" : "Đã đặt điểm") + " tại " + fmt(a) + ", " + fmt(b) + (inVanDon(a, b) ? "." : " – ngoài phạm vi Vân Đồn!"), inVanDon(a, b) ? "ok" : "warn"); }

    function build() {
      if (api) { api.resize(); return; }
      var make = function (G) {
        api = G ? GoogleMap(mapEl, pick) : LeafletMap(mapEl, pick);
        mapEl.dataset.engine = api.kind;
        var c = current();
        if (c) api.setMarker(c[0], c[1], true);
        if (G) setupGoogleSearch();
      };
      if (cfg.key) loadGoogle().then(function () { make(true); }, function () { make(false); say("Không tải được Google Maps, đang dùng bản đồ OpenStreetMap.", "warn"); });
      else make(false);
    }
    self.build = build;

    satBtn.addEventListener("click", function () {
      if (!api) return;
      var on = api.toggleSat();
      satBtn.setAttribute("aria-pressed", String(on));
      satBtn.textContent = on ? "Bản đồ" : "Vệ tinh";
    });

    /* Tìm địa danh */
    function showResults(list) {
      results.innerHTML = "";
      if (!list.length) { results.appendChild(VDH.el("li", { "class": "is-empty" }, "Không tìm thấy. Thử tên khác hoặc kéo bản đồ tới khu vực.")); results.hidden = false; return; }
      list.slice(0, 6).forEach(function (r) {
        var li = VDH.el("li");
        var b = VDH.el("button", { type: "button" }, r.name);
        b.addEventListener("click", function () {
          results.hidden = true;
          if (api) api.goTo(r.lat, r.lng, 17);
          say("Đã tới “" + r.name.split(",")[0] + "”. Bấm vào đúng vị trí trên bản đồ để đặt điểm.", "info");
        });
        li.appendChild(b);
        results.appendChild(li);
      });
      results.hidden = false;
    }
    function nominatim() {
      var term = q.value.trim();
      if (!term) return;
      var b = cfg.bounds;
      var url = cfg.nominatim + "?format=json&limit=6&countrycodes=vn&accept-language=vi&viewbox=" +
        [b.west - 0.3, b.north + 0.3, b.east + 0.3, b.south - 0.3].join(",") + "&q=" + encodeURIComponent(term);
      results.innerHTML = ""; results.appendChild(VDH.el("li", { "class": "is-empty" }, "Đang tìm…")); results.hidden = false;
      fetch(url, { headers: { "Accept": "application/json" } }).then(function (r) { return r.json(); }).then(function (data) {
        showResults((data || []).map(function (d) { return { name: d.display_name, lat: parseFloat(d.lat), lng: parseFloat(d.lon) }; }));
      }).catch(function () { results.innerHTML = ""; results.appendChild(VDH.el("li", { "class": "is-empty" }, "Không kết nối được dịch vụ tìm địa danh.")); });
    }
    var googleAuto = false;
    function setupGoogleSearch() {
      try {
        var g = window.google.maps;
        if (!g.places || !g.places.Autocomplete) return;
        var b = cfg.bounds;
        var ac = new g.places.Autocomplete(q, { bounds: { south: b.south, west: b.west, north: b.north, east: b.east },
          componentRestrictions: { country: "vn" }, fields: ["geometry", "name"] });
        ac.addListener("place_changed", function () {
          var p = ac.getPlace();
          if (p && p.geometry && p.geometry.location) {
            api.goTo(p.geometry.location.lat(), p.geometry.location.lng(), 17);
            say("Đã tới “" + (p.name || q.value) + "”. Bấm vào đúng vị trí để đặt điểm.", "info");
          }
        });
        googleAuto = true;
      } catch (e) { googleAuto = false; }
    }
    go.addEventListener("click", function () { if (!googleAuto) nominatim(); });
    q.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { e.preventDefault(); if (!googleAuto) nominatim(); }
      if (e.key === "Escape") results.hidden = true;
    });

    if (nameInp) nameInp.addEventListener("input", function () {
      var lab = row.querySelector(".inline_label");
      if (lab) lab.textContent = nameInp.value || "mới";
    });
    check();
    if (text.value && !current()) readText();
    if (!row.closest("[hidden]") && row.offsetParent !== null) build();
  }

  /* ---------------------------------------------------------- Điểm chính: chỉ một */
  function initMainPoint(root) {
    root.addEventListener("change", function (e) {
      var t = e.target;
      if (!t.name || !/-diem_chinh$/.test(t.name) || !t.checked) return;
      root.querySelectorAll("input[name$='-diem_chinh']").forEach(function (o) { if (o !== t) o.checked = false; });
    });
  }

  VDH.ready(function () {
    var cfgEl = document.getElementById("vdh-map-config");
    if (!cfgEl) return;
    cfg = JSON.parse(cfgEl.textContent);
    var group = document.querySelector(".vdh-points-group");
    if (!group) return;
    var list = group.querySelector(".vdh-points");
    function initAll() { group.querySelectorAll(".vdh-point").forEach(initPoint); }
    function buildVisible() {
      group.querySelectorAll(".vdh-point").forEach(function (r) { if (r._vdhPoint && r.offsetParent !== null) r._vdhPoint.build(); });
    }
    initAll();
    initMainPoint(group);
    document.addEventListener("vdh:tabshown", function (e) {
      if (e.target.contains(group)) setTimeout(buildVisible, 30);
    });
    document.addEventListener("formset:added", function (e) {
      if (!group.contains(e.target)) return;
      initPoint(e.target);
      if (e.target._vdhPoint) setTimeout(e.target._vdhPoint.build, 30);
      VDH.renumber(list, ".vdh-point");
    });
    if (list) {
      VDH.sortable(list, { items: ".vdh-point", handle: ".vdh-handle", onEnd: function () { VDH.renumber(list, ".vdh-point"); } });
      var form = group.closest("form");
      if (form) form.addEventListener("submit", function () { VDH.renumber(list, ".vdh-point"); });
    }
    setTimeout(buildVisible, 60);
  });
})();
