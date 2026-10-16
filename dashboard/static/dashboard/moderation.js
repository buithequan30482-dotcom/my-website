/* Hàng đợi kiểm duyệt: gửi thao tác bằng fetch, phím tắt j/k/x/a/h/s/r. Không có JS vẫn dùng được (POST thường). */
(function () {
  "use strict";
  var form = document.getElementById("vd-mod-form");
  if (!form) return;
  var flash = document.getElementById("vd-flash");
  var conLai = document.getElementById("vd-con-lai");
  var dem = document.getElementById("vd-dem");
  var all = document.getElementById("vd-all");
  var idx = 0;

  function items() { return Array.prototype.slice.call(form.querySelectorAll(".vd-item:not(.is-gone)")); }
  function boxes() { return Array.prototype.slice.call(form.querySelectorAll('.vd-item:not(.is-gone) input[name="ids"]')); }
  function capNhatDem() {
    var n = boxes().filter(function (b) { return b.checked; }).length;
    if (dem) dem.textContent = n + " đã chọn";
  }
  function chon(i) {
    var ds = items();
    if (!ds.length) return;
    idx = Math.max(0, Math.min(i, ds.length - 1));
    ds.forEach(function (el, j) { el.classList.toggle("is-active", j === idx); });
    ds[idx].focus({ preventScroll: true });
    ds[idx].scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
  function bao(msg, loi) {
    flash.hidden = false;
    flash.textContent = msg;
    flash.classList.toggle("is-err", !!loi);
    clearTimeout(bao._t);
    bao._t = setTimeout(function () { flash.hidden = true; }, 4000);
  }

  function gui(act) {
    var fd = new FormData(form);
    fd.set("act", act);
    return fetch(form.action, { method: "POST", body: fd, headers: { "X-Requested-With": "fetch" }, credentials: "same-origin" })
      .then(function (r) { return r.json().catch(function () { return { ok: false, message: "Lỗi máy chủ (" + r.status + ")." }; }); })
      .then(function (res) {
        bao(res.message, !res.ok);
        if (!res.ok) return;
        (res.ids || []).forEach(function (id) {
          var el = form.querySelector('.vd-item[data-id="' + id + '"]');
          if (!el) return;
          el.classList.add("is-gone");
          var cb = el.querySelector('input[name="ids"]'); if (cb) cb.checked = false;
          setTimeout(function () { el.remove(); if (!items().length) location.reload(); }, 260);
        });
        if (conLai && typeof res.con_lai === "number") conLai.textContent = res.con_lai.toLocaleString("vi-VN");
        if (all) all.checked = false;
        capNhatDem();
        setTimeout(function () { chon(idx); }, 280);
      })
      .catch(function () { bao("Không gửi được, vui lòng thử lại.", true); });
  }

  // Bấm nút: chặn submit thường, gửi bằng fetch
  form.addEventListener("click", function (e) {
    var btn = e.target.closest('button[name="act"]');
    if (!btn) return;
    e.preventDefault();
    var item = btn.closest(".vd-item");
    if (item) idx = items().indexOf(item);
    gui(btn.value);
  });
  form.addEventListener("change", function (e) {
    if (e.target === all) boxes().forEach(function (b) { b.checked = all.checked; });
    capNhatDem();
  });

  // Phím tắt (bỏ qua khi đang gõ)
  document.addEventListener("keydown", function (e) {
    var t = e.target;
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (t && (t.tagName === "TEXTAREA" || t.tagName === "INPUT" && t.type !== "checkbox" || t.tagName === "SELECT" || t.isContentEditable)) {
      if (e.key === "Escape") t.blur();
      return;
    }
    var ds = items(), cur = ds[idx];
    var map = { a: "approve", h: "hide", s: "spam" };
    if (e.key === "j") { chon(idx + 1); e.preventDefault(); }
    else if (e.key === "k") { chon(idx - 1); e.preventDefault(); }
    else if (e.key === "x" && cur) { var cb = cur.querySelector('input[name="ids"]'); if (cb) { cb.checked = !cb.checked; capNhatDem(); } }
    else if (map[e.key] && cur) { e.preventDefault(); gui(map[e.key] + ":" + cur.dataset.id); }
    else if (e.key === "r" && cur) {
      var d = cur.querySelector(".vd-reply");
      if (d) { d.open = true; e.preventDefault(); d.querySelector("textarea").focus(); }
    }
  });

  form.addEventListener("click", function (e) {
    var item = e.target.closest(".vd-item");
    if (item) { var i = items().indexOf(item); if (i >= 0 && i !== idx) chon(i); }
  }, true);
  chon(0);
})();
