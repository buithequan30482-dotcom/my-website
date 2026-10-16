/* Màn hình sửa di tích: thẻ (tabs), trình hướng dẫn 5 bước, lưu nháp tự động (localStorage),
 * đối chiếu bản tiếng Việt ở thẻ dịch, danh sách kiểm tra (TR FR-A03, FR-H02). */
(function () {
  "use strict";
  var VDH = window.VDH = window.VDH || {};
  var AUTOSAVE_MS = 60000;
  var SKIP_NAME = /(csrfmiddlewaretoken|TOTAL_FORMS|INITIAL_FORMS|MIN_NUM_FORMS|MAX_NUM_FORMS|^_)/;

  VDH.ready(function () {
    var form = document.querySelector("body.vdh-ditich-form #ditich_form") ||
               document.querySelector("body.vdh-ditich-form form[method=post]");
    if (!form) return;
    var panels = Array.prototype.slice.call(form.querySelectorAll(".vdh-panel"));
    var tabs = Array.prototype.slice.call(form.querySelectorAll(".vdh-tab"));
    var tabInput = document.getElementById("vdh-tab-input");
    var meta = document.getElementById("vdh-form-meta");
    var wizard = meta && meta.dataset.wizard === "1";

    /* ---------------------------------------------------------- Thẻ */
    function panelHasError(p) {
      return !!p.querySelector(".errorlist li, .errors .errorlist, .vdh-field.errors");
    }
    function showPanels(ids) {
      panels.forEach(function (p) {
        var on = ids.indexOf(p.dataset.tab) >= 0;
        p.hidden = !on;
        p.classList.toggle("is-active", on);
        if (on) p.dispatchEvent(new CustomEvent("vdh:tabshown", { bubbles: true }));
      });
      tabs.forEach(function (t) {
        var on = ids.indexOf(t.dataset.tab) >= 0;
        t.classList.toggle("is-active", on);
        t.setAttribute("aria-selected", String(on));
        t.tabIndex = on ? 0 : -1;
      });
      if (tabInput) tabInput.value = ids[0] || "";
    }
    VDH.showTab = function (id, focus) {
      if (wizard) {
        var step = stepForTab(id);
        if (step) return goStep(step);
      }
      showPanels([id]);
      try { history.replaceState(null, "", "#tab=" + id); } catch (e) { /* bỏ qua */ }
      if (focus) {
        var t = form.querySelector(".vdh-tab[data-tab='" + id + "']");
        if (t) t.focus();
      }
    };
    tabs.forEach(function (t, i) {
      t.addEventListener("click", function () { VDH.showTab(t.dataset.tab); });
      t.addEventListener("keydown", function (e) {
        var j = e.key === "ArrowRight" ? i + 1 : e.key === "ArrowLeft" ? i - 1 : null;
        if (j === null) return;
        e.preventDefault();
        var n = tabs[(j + tabs.length) % tabs.length];
        VDH.showTab(n.dataset.tab, true);
      });
    });
    var errorTabs = [];
    panels.forEach(function (p) {
      if (!panelHasError(p)) return;
      errorTabs.push(p.dataset.tab);
      var t = form.querySelector(".vdh-tab[data-tab='" + p.dataset.tab + "']");
      if (t) { t.classList.add("has-error"); t.querySelector(".vdh-err-dot").hidden = false; }
    });
    document.querySelectorAll("[data-goto-tab]").forEach(function (b) {
      b.addEventListener("click", function () {
        VDH.showTab(b.getAttribute("data-goto-tab"));
        var p = document.getElementById("vdh-panel-" + b.getAttribute("data-goto-tab"));
        if (p) p.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });

    /* ---------------------------------------------------------- Trình hướng dẫn */
    var steps = Array.prototype.slice.call(form.querySelectorAll(".vdh-step"));
    var current = 1;
    var wizInput = document.getElementById("vdh-wizard-input");
    function stepForTab(tab) {
      for (var i = 0; i < steps.length; i++) {
        if (steps[i].dataset.tabs.split(" ").indexOf(tab) >= 0) return i + 1;
      }
      return 0;
    }
    function goStep(n) {
      n = Math.max(1, Math.min(steps.length, n));
      current = n;
      var s = steps[n - 1];
      showPanels(s.dataset.tabs.split(" "));
      steps.forEach(function (b, i) {
        b.classList.toggle("is-active", i === n - 1);
        b.classList.toggle("is-done", i < n - 1);
        b.setAttribute("aria-current", i === n - 1 ? "step" : "false");
      });
      var bar = document.getElementById("vdh-progress-bar");
      if (bar) bar.style.width = ((n - 1) / (steps.length - 1) * 100) + "%";
      if (wizInput) wizInput.value = n;
      var prev = form.querySelector(".vdh-prev"), next = form.querySelector(".vdh-next"), send = form.querySelector(".vdh-send");
      if (prev) prev.disabled = n === 1;
      if (next) next.hidden = n === steps.length;
      if (send) send.hidden = n !== steps.length;
      if (n === steps.length) updateChecklist();
      try { history.replaceState(null, "", "#step=" + n); } catch (e) { /* bỏ qua */ }
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
    if (wizard) {
      steps.forEach(function (b, i) {
        b.addEventListener("click", function () { tryGo(i + 1); });
        var hasErr = b.dataset.tabs.split(" ").some(function (t) { return errorTabs.indexOf(t) >= 0; });
        if (hasErr) { b.classList.add("has-error"); b.querySelector(".vdh-err-dot").hidden = false; }
      });
      var prevBtn = form.querySelector(".vdh-prev"), nextBtn = form.querySelector(".vdh-next");
      if (prevBtn) prevBtn.addEventListener("click", function () { goStep(current - 1); });
      if (nextBtn) nextBtn.addEventListener("click", function () { tryGo(current + 1); });
    }
    function saved() { return meta && meta.dataset.saved === "1"; }
    function tryGo(n) {
      // Bước Ảnh cần di tích đã lưu: tự lưu nháp rồi tiếp tục.
      if (n >= 3 && !saved()) {
        var missing = [];
        [["ma", "Mã di tích"], ["ten_vi", "Tên"], ["cap_xep_hang", "Cấp xếp hạng"], ["khu_vuc", "Khu vực"],
         ["dia_chi_moi_vi", "Địa điểm từ 01/7/2025"]].forEach(function (f) {
          var el = form.elements[f[0]];
          if (el && !String(el.value || "").trim()) missing.push(f[1]);
        });
        var lh = form.querySelectorAll("input[name=loai_hinh]:checked");
        if (form.querySelector("input[name=loai_hinh]") && !lh.length) missing.push("Loại hình");
        if (missing.length) {
          goStep(1);
          alert("Để lưu nháp và sang bước tải ảnh, hãy điền: " + missing.join(", ") + ".");
          return;
        }
        if (wizInput) wizInput.value = n;
        var b = document.createElement("input");
        b.type = "hidden"; b.name = "_vd_draft"; b.value = "1";
        form.appendChild(b);
        clearDraft();
        if (form.requestSubmit) form.requestSubmit(); else form.submit();
        return;
      }
      goStep(n);
    }

    /* ---------------------------------------------------------- Danh sách kiểm tra (bước 5) */
    function val(name) {
      var el = form.elements[name];
      if (!el) return "";
      if (el._quill) return el._quill.getText().trim();
      return String(el.value || "").trim();
    }
    function updateChecklist() {
      var list = document.getElementById("vdh-checklist");
      if (!list) return;
      var lats = Array.prototype.slice.call(form.querySelectorAll(".vdh-point:not(.empty-form) input.vdh-lat"))
        .filter(function (i) { var d = i.closest(".vdh-point").querySelector("input[name$='-DELETE']"); return !(d && d.checked); });
      var withCoord = lats.filter(function (i) { return i.value !== ""; }).length;
      var gallery = VDH.galleryState ? VDH.galleryState() : { real: parseInt(list.dataset.realImages || "0", 10) };
      var res = {
        ten: !!val("ten_vi"), tom_tat: !!val("tom_tat_vi"), cap: !!val("cap_xep_hang"), khu_vuc: !!val("khu_vuc"),
        anh_dai_dien: !!val("anh_dai_dien"), toa_do: withCoord > 0, toa_do_du: lats.length > 0 && withCoord === lats.length,
        anh_that: gallery.real > 0, noi_dung: !!val("noi_dung_vi"), tham_quan: !!val("thong_tin_tham_quan_vi"),
        en: !!(val("ten_en") && val("tom_tat_en")), zh: !!(val("ten_zh_hans") && val("tom_tat_zh_hans"))
      };
      var req = 0;
      list.querySelectorAll("li").forEach(function (li) {
        var ok = !!res[li.dataset.check];
        li.classList.toggle("is-ok", ok);
        li.classList.toggle("is-miss", !ok);
        if (!ok && li.dataset.level === "req") req += 1;
        if (!li.dataset.bound && li.dataset.step) {
          li.dataset.bound = "1";
          li.tabIndex = 0;
          li.setAttribute("role", "button");
          li.addEventListener("click", function () { goStep(parseInt(li.dataset.step, 10)); });
          li.addEventListener("keydown", function (e) { if (e.key === "Enter") goStep(parseInt(li.dataset.step, 10)); });
        }
      });
      var sum = document.getElementById("vdh-check-summary");
      if (sum) {
        sum.textContent = req ? ("Còn " + req + " mục bắt buộc chưa có. Vẫn có thể gửi duyệt, nhưng người duyệt chưa xuất bản được.")
          : "Đủ điều kiện bắt buộc. Có thể gửi duyệt.";
        sum.className = "vdh-check-summary " + (req ? "is-miss" : "is-ok");
      }
    }
    VDH.updateChecklist = updateChecklist;

    /* ---------------------------------------------------------- Đối chiếu bản tiếng Việt ở thẻ dịch */
    function htmlToFragment(html) {
      var doc = new DOMParser().parseFromString("<div>" + (html || "") + "</div>", "text/html");
      var frag = document.createDocumentFragment();
      var blocks = doc.body.querySelectorAll("h2,h3,h4,p,li,blockquote");
      if (!blocks.length) {
        var t = doc.body.textContent.trim();
        if (t) frag.appendChild(VDH.el("p", {}, t));
        return frag;
      }
      blocks.forEach(function (b) {
        var txt = b.textContent.trim();
        if (!txt) return;
        var tag = /^H[234]$/.test(b.tagName) ? "strong" : "p";
        var e = VDH.el(tag, { "class": "vdh-ref-" + b.tagName.toLowerCase() }, (b.tagName === "LI" ? "• " : "") + txt);
        frag.appendChild(e);
      });
      return frag;
    }
    form.querySelectorAll(".vdh-translation .form-row, .vdh-translation .fieldBox").forEach(function (row) {
      var inp = row.querySelector("input[name$='_en'], textarea[name$='_en'], input[name$='_zh_hans'], textarea[name$='_zh_hans']");
      if (!inp || row.querySelector(".vdh-ref") || (row.classList.contains("form-row") && row.querySelector(".fieldBox"))) return;
      var viName = inp.name.replace(/_(en|zh_hans)$/, "_vi");
      var vi = form.elements[viName];
      if (!vi) return;
      var det = VDH.el("details", { "class": "vdh-ref" });
      det.appendChild(VDH.el("summary", {}, "Xem bản tiếng Việt"));
      var body = VDH.el("div", { "class": "vdh-ref-body", lang: "vi" });
      det.appendChild(body);
      det.addEventListener("toggle", function () {
        if (!det.open) return;
        body.innerHTML = "";
        var v = vi.value || "";
        if (!v.trim()) body.appendChild(VDH.el("em", {}, "(bản tiếng Việt đang trống)"));
        else if (vi.classList.contains("vdh-richtext")) body.appendChild(htmlToFragment(v));
        else body.appendChild(VDH.el("p", {}, v));
      });
      var holder = row.querySelector(".flex-container") ? row : row;
      holder.classList.add("vdh-has-ref");
      holder.appendChild(det);
    });

    /* ---------------------------------------------------------- Lưu nháp tự động (localStorage) */
    var key = "vdh-draft:" + location.pathname;
    var status = document.getElementById("vdh-autosave-status");
    function serialize() {
      var out = {};
      Array.prototype.forEach.call(form.elements, function (el) {
        if (!el.name || SKIP_NAME.test(el.name) || el.type === "file" || el.type === "submit" || el.type === "button") return;
        if (el.closest(".empty-form")) return;
        if (el.type === "checkbox" || el.type === "radio") {
          if (el.type === "radio" && !el.checked) return;
          var k = el.name + (el.type === "checkbox" ? "::" + el.value : "");
          out[k] = el.type === "checkbox" ? el.checked : el.value;
          return;
        }
        if (el.tagName === "SELECT" && el.multiple) {
          out[el.name] = Array.prototype.filter.call(el.options, function (o) { return o.selected; }).map(function (o) { return o.value; });
          return;
        }
        if (el._quill) { el.value = el.value; }
        out[el.name] = el.value;
      });
      return out;
    }
    var baseline = JSON.stringify(serialize());
    function store(get) {
      try { return get ? localStorage.getItem(key) : null; } catch (e) { return null; }
    }
    function clearDraft() { try { localStorage.removeItem(key); } catch (e) { /* bỏ qua */ } }
    VDH.clearDraft = clearDraft;
    function pad(n) { return (n < 10 ? "0" : "") + n; }
    function autosave() {
      var data = serialize();
      var s = JSON.stringify(data);
      if (s === baseline) return;
      try {
        localStorage.setItem(key, JSON.stringify({ ts: Date.now(), data: data }));
        var d = new Date();
        if (status) status.textContent = "Đã lưu nháp tạm trên máy này lúc " + pad(d.getHours()) + ":" + pad(d.getMinutes()) +
          " (chưa gửi lên máy chủ – bấm Lưu để lưu chính thức).";
      } catch (e) {
        if (status) status.textContent = "Không lưu nháp tạm được trên trình duyệt này.";
      }
    }
    setInterval(autosave, AUTOSAVE_MS);
    form.addEventListener("submit", clearDraft);
    window.addEventListener("beforeunload", function () { /* giữ bản nháp tạm nếu rời trang chưa lưu */ });

    function restore(data) {
      Object.keys(data).forEach(function (k) {
        var v = data[k];
        if (k.indexOf("::") > 0) {
          var p = k.split("::");
          form.querySelectorAll("input[type=checkbox]").forEach(function (c) {
            if (c.name === p[0] && c.value === p[1]) c.checked = !!v;
          });
          return;
        }
        var el = form.elements[k];
        if (!el) return;
        if (el instanceof RadioNodeList || (el.length && !el.tagName)) {
          Array.prototype.forEach.call(el, function (r) { if (r.type === "radio") r.checked = r.value === v; });
          return;
        }
        if (el.tagName === "SELECT" && el.multiple && Array.isArray(v)) {
          Array.prototype.forEach.call(el.options, function (o) { o.selected = v.indexOf(o.value) >= 0; });
        } else if (el._vdhSetHtml) {
          el._vdhSetHtml(v);
        } else {
          el.value = v;
        }
        el.dispatchEvent(new Event("change", { bubbles: true }));
      });
    }
    (function offerRestore() {
      var raw = store(true);
      if (!raw) return;
      var draft;
      try { draft = JSON.parse(raw); } catch (e) { clearDraft(); return; }
      var modified = meta ? parseInt(meta.dataset.modified || "0", 10) : 0;
      if (!draft || !draft.data || (modified && draft.ts < modified) || Date.now() - draft.ts > 14 * 864e5) { clearDraft(); return; }
      if (JSON.stringify(draft.data) === baseline) { clearDraft(); return; }
      var box = document.getElementById("vdh-restore");
      if (!box) return;
      var d = new Date(draft.ts);
      box.querySelector(".vdh-autosave-text").textContent = "Có bản nháp chưa lưu trên máy này lúc " + pad(d.getHours()) + ":" +
        pad(d.getMinutes()) + " ngày " + pad(d.getDate()) + "/" + pad(d.getMonth() + 1) + ". Khôi phục để tiếp tục soạn?";
      box.hidden = false;
      box.querySelector(".vdh-restore-yes").addEventListener("click", function () {
        restore(draft.data);
        box.hidden = true;
        if (status) status.textContent = "Đã khôi phục bản nháp. Kiểm tra lại rồi bấm Lưu.";
      });
      box.querySelector(".vdh-restore-no").addEventListener("click", function () { clearDraft(); box.hidden = true; });
    })();

    /* ---------------------------------------------------------- Khởi động */
    var m = location.hash.match(/(tab|step)=([a-z0-9]+)/);
    if (wizard) {
      var first = 1;
      if (errorTabs.length) first = stepForTab(errorTabs[0]) || 1;
      else if (m && m[1] === "step") first = parseInt(m[2], 10) || 1;
      goStep(first);
    } else {
      var start = errorTabs[0] || (m && m[1] === "tab" && form.querySelector(".vdh-panel[data-tab='" + m[2] + "']") ? m[2] : null) || "chung";
      showPanels([start]);
    }
    if (errorTabs.length) {
      var firstErr = form.querySelector(".vdh-panel.is-active .errorlist, .vdh-panel.is-active .errors");
      if (firstErr) setTimeout(function () { firstErr.scrollIntoView({ block: "center" }); }, 50);
    }
    form.addEventListener("submit", function () {
      var send = document.activeElement;
      if (send && send.classList && send.classList.contains("vdh-send")) { /* gửi duyệt */ }
    });
  });
})();
