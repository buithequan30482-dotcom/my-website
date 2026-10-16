/* Khu quản trị nội dung di tích – tiện ích chung (JS thuần, không phụ thuộc thư viện).
 * - VDH.ready, VDH.csrf, VDH.post (fetch kèm CSRF)
 * - VDH.sortable: kéo thả sắp thứ tự bằng Pointer Events (chuột + cảm ứng)
 * - Nút (?) trợ giúp chi tiết cho trường có data-help (TR FR-H01)
 * - Bộ đếm ký tự (data-counter), sắp xếp inline (.vdh-sortable), ảnh bìa YouTube
 * - Thư viện ảnh: chuyển lưới / bảng; trang xem trước nhập Excel: đổi chế độ
 */
(function () {
  "use strict";
  if (window.VDH && window.VDH._common) return;
  var VDH = window.VDH = window.VDH || {};
  VDH._common = true;

  VDH.ready = function (fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  };

  VDH.csrf = function () {
    var inp = document.querySelector("input[name=csrfmiddlewaretoken]");
    if (inp) return inp.value;
    var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  };

  VDH.post = function (url, data) {
    var body = new FormData();
    Object.keys(data || {}).forEach(function (k) { body.append(k, data[k]); });
    return fetch(url, {
      method: "POST", body: body, credentials: "same-origin",
      headers: { "X-CSRFToken": VDH.csrf(), "X-Requested-With": "XMLHttpRequest" }
    }).then(function (r) {
      return r.json().catch(function () { return { ok: false, error: "Lỗi máy chủ (" + r.status + ")." }; })
        .then(function (j) { if (!r.ok && j.ok !== false) j.ok = false; return j; });
    }, function () { return { ok: false, error: "Mất kết nối mạng. Hãy thử lại." }; });
  };

  VDH.el = function (tag, attrs, text) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "class") e.className = attrs[k]; else e.setAttribute(k, attrs[k]);
    });
    if (text != null) e.textContent = text;
    return e;
  };

  /* ---------------------------------------------------------------- Kéo thả sắp xếp
   * opts: {items: selector phần tử con, handle: selector tay cầm (tùy chọn), grid: bool, onEnd: fn(container)} */
  VDH.sortable = function (container, opts) {
    opts = opts || {};
    var dragging = null, pointerId = null, moved = false;

    function itemFrom(target) {
      var it = target && target.closest ? target.closest(opts.items) : null;
      return it && it.parentNode === container ? it : null;
    }
    container.addEventListener("pointerdown", function (e) {
      if (e.button !== 0) return;
      if (opts.handle && !(e.target.closest && e.target.closest(opts.handle))) return;
      if (e.target.closest("input,textarea,select,button,a,label,summary")) return;
      var it = itemFrom(e.target);
      if (!it || it.classList.contains("empty-form")) return;
      dragging = it; pointerId = e.pointerId; moved = false;
      try { container.setPointerCapture(pointerId); } catch (err) { /* bỏ qua */ }
      it.classList.add("vdh-dragging");
      document.body.classList.add("vdh-no-select");
      e.preventDefault();
    });
    container.addEventListener("pointermove", function (e) {
      if (!dragging || e.pointerId !== pointerId) return;
      var under = document.elementFromPoint(e.clientX, e.clientY);
      var target = itemFrom(under);
      if (!target || target === dragging || target.classList.contains("empty-form")) return;
      var r = target.getBoundingClientRect();
      var after = opts.grid ? (e.clientX > r.left + r.width / 2) : (e.clientY > r.top + r.height / 2);
      container.insertBefore(dragging, after ? target.nextSibling : target);
      moved = true;
    });
    function end(e) {
      if (!dragging || (e && e.pointerId !== pointerId)) return;
      dragging.classList.remove("vdh-dragging");
      document.body.classList.remove("vdh-no-select");
      try { container.releasePointerCapture(pointerId); } catch (err) { /* bỏ qua */ }
      var was = moved;
      dragging = null; pointerId = null; moved = false;
      if (was && opts.onEnd) opts.onEnd(container);
    }
    container.addEventListener("pointerup", end);
    container.addEventListener("pointercancel", end);
  };

  /* ---------------------------------------------------------------- Trợ giúp (?) */
  VDH.initHelp = function (root) {
    (root || document).querySelectorAll("[data-help]").forEach(function (inp) {
      if (inp.dataset.helpReady || inp.closest(".empty-form")) return;
      inp.dataset.helpReady = "1";
      var box = inp.closest(".fieldBox") || inp.closest(".vdh-field") || inp.closest(".form-row");
      if (!box) return;
      var label = box.querySelector("label");
      if (!label) return;
      var btn = VDH.el("button", { type: "button", "class": "vdh-q", "aria-expanded": "false",
        "aria-label": "Giải thích chi tiết", title: "Giải thích chi tiết, ví dụ" }, "?");
      var detail = VDH.el("div", { "class": "vdh-help-detail", role: "note" }, inp.getAttribute("data-help"));
      detail.hidden = true;
      label.appendChild(btn);
      var help = box.querySelector(".help");
      (help || inp).insertAdjacentElement("afterend", detail);
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        detail.hidden = !detail.hidden;
        btn.setAttribute("aria-expanded", String(!detail.hidden));
      });
    });
  };

  /* ---------------------------------------------------------------- Đếm ký tự */
  VDH.initCounters = function (root) {
    (root || document).querySelectorAll("[data-counter]").forEach(function (inp) {
      if (inp.dataset.counterReady || inp.closest(".empty-form")) return;
      inp.dataset.counterReady = "1";
      var max = parseInt(inp.getAttribute("data-counter"), 10);
      var out = VDH.el("span", { "class": "vdh-counter", "aria-live": "polite" });
      inp.insertAdjacentElement("afterend", out);
      function upd() {
        var n = inp.value.length;
        out.textContent = n + " / " + max + " ký tự";
        out.classList.toggle("is-over", n > max);
      }
      inp.addEventListener("input", upd);
      upd();
    });
  };

  /* ---------------------------------------------------------------- Inline sắp xếp được */
  function isBlankExtra(row) {
    var idInp = row.querySelector("input[type=hidden][name$='-id']");
    if (idInp && idInp.value) return false;
    // Dòng mới chưa nhập gì (mọi ô giữ giá trị ban đầu) – không đánh số để Django bỏ qua dòng này.
    var fields = row.querySelectorAll("input:not([type=hidden]), select, textarea");
    for (var i = 0; i < fields.length; i++) {
      var f = fields[i];
      if (f.type === "checkbox" || f.type === "radio") { if (f.checked !== f.defaultChecked) return false; }
      else if (f.tagName === "SELECT") {
        for (var j = 0; j < f.options.length; j++) if (f.options[j].selected !== f.options[j].defaultSelected) return false;
      }
      else if (f.type === "file") { if (f.value) return false; }
      else if (f.value !== f.defaultValue) return false;
    }
    return true;
  }
  VDH.renumber = function (container, rowSel) {
    var i = 0;
    container.querySelectorAll(rowSel).forEach(function (row) {
      if (row.classList.contains("empty-form")) return;
      var ord = row.querySelector("input.vdh-order");
      if (!ord) return;
      i += 1;
      if (isBlankExtra(row)) return;
      ord.value = i;
    });
  };
  VDH.initSortableInlines = function () {
    document.querySelectorAll(".inline-group").forEach(function (group) {
      var fs = group.querySelector("fieldset.vdh-sortable");
      if (!fs || group.dataset.sortReady) return;
      group.dataset.sortReady = "1";
      var tabular = group.getAttribute("data-inline-type") === "tabular";
      var container = tabular ? fs.querySelector("tbody") : fs;
      var rowSel = tabular ? "tr.form-row" : ".inline-related";
      function addHandles() {
        container.querySelectorAll(rowSel).forEach(function (row) {
          if (row.querySelector(".vdh-handle")) return;
          var h = VDH.el("span", { "class": "vdh-handle", title: "Kéo để sắp thứ tự", "aria-hidden": "true" }, "⠿");
          var place = tabular ? (row.querySelector("td.original") || row.querySelector("td")) : row.querySelector("h3");
          if (place) place.insertBefore(h, place.firstChild);
        });
      }
      addHandles();
      document.addEventListener("formset:added", addHandles);
      VDH.sortable(container, { items: rowSel, handle: ".vdh-handle", onEnd: function () { VDH.renumber(container, rowSel); } });
      var form = group.closest("form");
      if (form) form.addEventListener("submit", function () { VDH.renumber(container, rowSel); });
    });
  };

  /* ---------------------------------------------------------------- Ảnh bìa YouTube */
  VDH.youtubeId = function (url) {
    var m = String(url || "").match(/(?:v=|youtu\.be\/|embed\/|shorts\/|live\/)([A-Za-z0-9_-]{11})/);
    return m ? m[1] : "";
  };
  VDH.initYoutube = function (root) {
    (root || document).querySelectorAll("input.vdh-yt-input, input[name$='youtube_url']").forEach(function (inp) {
      if (inp.dataset.ytReady || inp.closest(".empty-form")) return;
      inp.dataset.ytReady = "1";
      var box = VDH.el("div", { "class": "vdh-yt-preview" });
      inp.insertAdjacentElement("afterend", box);
      function upd() {
        var id = VDH.youtubeId(inp.value);
        box.innerHTML = "";
        if (!inp.value) return;
        if (!id) { box.appendChild(VDH.el("span", { "class": "vdh-warn-text" }, "Liên kết chưa đúng dạng YouTube.")); return; }
        var img = VDH.el("img", { src: "https://i.ytimg.com/vi/" + id + "/hqdefault.jpg", alt: "Ảnh bìa video", loading: "lazy" });
        box.appendChild(img);
      }
      inp.addEventListener("change", upd);
      inp.addEventListener("input", upd);
      upd();
    });
  };

  /* ---------------------------------------------------------------- Thư viện ảnh: lưới / bảng */
  function initLibraryToggle() {
    var btn = document.querySelector(".vdh-view-toggle");
    if (!btn) return;
    var key = "vdh-lib-view";
    var mode = "grid";
    try { mode = localStorage.getItem(key) || "grid"; } catch (e) { /* bỏ qua */ }
    function apply() {
      document.body.classList.toggle("vdh-lib-table", mode === "table");
      btn.textContent = mode === "table" ? btn.dataset.tableLabel : btn.dataset.gridLabel;
    }
    btn.addEventListener("click", function () {
      mode = mode === "table" ? "grid" : "table";
      try { localStorage.setItem(key, mode); } catch (e) { /* bỏ qua */ }
      apply();
    });
    apply();
  }

  /* ---------------------------------------------------------------- Xem trước nhập Excel */
  function initImportPreview() {
    var root = document.querySelector("[data-import-preview]");
    if (!root) return;
    var sumEl = document.getElementById("vdh-import-summary");
    var sums = sumEl ? JSON.parse(sumEl.textContent) : {};
    function apply() {
      var checked = root.querySelector("input[name=mode]:checked");
      var mode = checked ? checked.value : "new";
      root.classList.toggle("is-mode-update", mode === "update");
      root.querySelectorAll(".vdh-irow").forEach(function (tr) {
        var bad = tr.dataset.skip !== "1" && parseInt(tr.getAttribute("data-err-" + mode), 10) > 0;
        tr.classList.toggle("is-bad", bad);
        tr.classList.toggle("is-ok", !bad && tr.dataset.skip !== "1");
      });
      var s = sums[mode] || {};
      root.querySelectorAll("[data-sum]").forEach(function (el) {
        var k = el.getAttribute("data-sum");
        if (s[k] != null) el.textContent = s[k];
      });
      var btn = root.querySelector(".vdh-confirm-btn");
      if (btn) btn.disabled = !s.valid;
    }
    root.querySelectorAll("input[name=mode]").forEach(function (r) { r.addEventListener("change", apply); });
    apply();
    var form = root.querySelector("form");
    if (form) form.addEventListener("submit", function (e) {
      var s = sums[(root.querySelector("input[name=mode]:checked") || {}).value || "new"] || {};
      if (!window.confirm("Nhập " + (s.valid || 0) + " dòng hợp lệ vào hệ thống (trạng thái Nháp)? Các dòng lỗi sẽ bị bỏ qua.")) e.preventDefault();
    });
  }

  VDH.ready(function () {
    VDH.initHelp();
    VDH.initCounters();
    VDH.initSortableInlines();
    VDH.initYoutube();
    initLibraryToggle();
    initImportPreview();
    document.addEventListener("formset:added", function (e) {
      VDH.initHelp(e.target);
      VDH.initCounters(e.target);
      VDH.initYoutube(e.target);
    });
  });
})();
