/* Thẻ "Ảnh, video": tải nhiều ảnh (kéo thả, XHR có tiến trình), lưới ảnh với ★ ảnh đại diện, chú thích 3 ngôn ngữ,
 * tác giả, nguồn (lưu ngay khi rời ô), xóa, kéo thả sắp thứ tự (TR FR-A05, FR-H06). */
(function () {
  "use strict";
  var VDH = window.VDH = window.VDH || {};
  var MAX = 25 * 1024 * 1024;
  var OK_EXT = /\.(jpe?g|png|webp|heic|heif)$/i;

  VDH.ready(function () {
    var dataEl = document.getElementById("vdh-gallery-data");
    if (!dataEl) return;
    var data = JSON.parse(dataEl.textContent);
    var urls = data.urls || {};
    var items = data.items || [];
    var grid = document.getElementById("vdh-gallery");
    var tpl = document.getElementById("vdh-card-tpl");
    var empty = document.getElementById("vdh-gallery-empty");
    var count = document.getElementById("vdh-gallery-count");
    var select = document.querySelector("select[name=anh_dai_dien]");

    function u(kind, id) { return (urls[kind] || "").replace(urls.placeholder, String(id)); }

    VDH.galleryState = function () {
      var real = items.filter(function (i) { return !i.la_minh_hoa; }).length;
      return { total: items.length, real: real };
    };
    function refreshMeta() {
      if (count) count.textContent = items.length ? "(" + items.length + " ảnh – kéo ⠿ để sắp thứ tự)" : "";
      if (empty) empty.hidden = items.length > 0;
      if (VDH.updateChecklist) VDH.updateChecklist();
    }
    function setAvatarUI(id) {
      items.forEach(function (i) { i.avatar = i.id === id; });
      if (!grid) return;
      grid.querySelectorAll(".vdh-card").forEach(function (c) {
        var on = parseInt(c.dataset.id, 10) === id;
        c.classList.toggle("is-avatar", on);
        var st = c.querySelector(".vdh-star");
        st.setAttribute("aria-pressed", String(on));
        st.title = on ? "Đang là ảnh đại diện" : "Đặt làm ảnh đại diện";
        c.querySelector(".vdh-avatar-tag").hidden = !on;
      });
      if (select) {
        if (id && !select.querySelector("option[value='" + id + "']")) {
          select.appendChild(new Option("Ảnh #" + id, String(id)));
        }
        select.value = id ? String(id) : "";
        select.defaultValue = select.value;
        Array.prototype.forEach.call(select.options, function (o) { o.defaultSelected = o.selected; });
      }
    }

    function card(it) {
      var node = tpl.content.firstElementChild.cloneNode(true);
      node.dataset.id = it.id;
      var img = node.querySelector("img");
      img.src = it.thumb;
      img.alt = it.chu_thich_vi || ("Ảnh " + it.id);
      node.querySelector(".vdh-card-open").href = it.large || it.thumb;
      node.querySelector(".vdh-card-size").textContent = it.width ? (it.width + " × " + it.height + " px") : "";
      node.querySelector(".vdh-ph-label").hidden = !it.la_minh_hoa;
      node.querySelector(".vdh-small-label").hidden = !(it.small && !it.la_minh_hoa);
      if (it.small) node.querySelector(".vdh-small-label").title = "Nhỏ hơn " + data.min_width + " px chiều ngang";
      if (it.la_minh_hoa) node.classList.add("is-placeholder");
      var msg = node.querySelector(".vdh-card-msg");
      node.querySelectorAll("input[data-f]").forEach(function (inp) {
        var f = inp.getAttribute("data-f");
        inp.value = it[f] || "";
        inp.dataset.saved = inp.value;
        if (!data.can_edit) { inp.readOnly = true; return; }
        inp.addEventListener("change", function () { saveField(it, inp, msg); });
        inp.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); inp.blur(); } });
      });
      var star = node.querySelector(".vdh-star");
      star.addEventListener("click", function () {
        if (!data.can_edit) return;
        msg.textContent = "Đang đặt ảnh đại diện…";
        VDH.post(u("avatar", it.id), {}).then(function (r) {
          if (!r.ok) { msg.textContent = r.error; msg.className = "vdh-card-msg is-error"; return; }
          setAvatarUI(it.id);
          msg.textContent = r.message; msg.className = "vdh-card-msg is-ok";
        });
      });
      var del = node.querySelector(".vdh-del");
      if (!data.can_delete) del.hidden = true;
      del.addEventListener("click", function () {
        var label = it.chu_thich_vi || it.name || ("#" + it.id);
        if (!window.confirm("Xóa ảnh “" + label + "”? Thao tác này không hoàn tác được.")) return;
        msg.textContent = "Đang xóa…";
        VDH.post(u("delete", it.id), {}).then(function (r) {
          if (!r.ok) { msg.textContent = r.error; msg.className = "vdh-card-msg is-error"; return; }
          items = items.filter(function (i) { return i.id !== it.id; });
          node.remove();
          if (select) {
            var o = select.querySelector("option[value='" + it.id + "']");
            if (o) o.remove();
            if (r.was_avatar) setAvatarUI(null);
          }
          refreshMeta();
        });
      });
      return node;
    }
    function saveField(it, inp, msg) {
      var f = inp.getAttribute("data-f");
      var v = inp.value.trim();
      if (f === "nguon" && !v) {
        msg.textContent = "Nguồn / bản quyền là bắt buộc."; msg.className = "vdh-card-msg is-error";
        inp.value = inp.dataset.saved; return;
      }
      var payload = {}; payload[f] = v;
      inp.classList.add("is-saving");
      VDH.post(u("update", it.id), payload).then(function (r) {
        inp.classList.remove("is-saving");
        if (!r.ok) { msg.textContent = r.error; msg.className = "vdh-card-msg is-error"; inp.value = inp.dataset.saved; return; }
        it[f] = v; inp.dataset.saved = v;
        msg.textContent = "Đã lưu."; msg.className = "vdh-card-msg is-ok";
        setTimeout(function () { if (msg.textContent === "Đã lưu.") msg.textContent = ""; }, 2500);
      });
    }

    if (grid && tpl) {
      items.forEach(function (it) { grid.appendChild(card(it)); });
      setAvatarUI((items.filter(function (i) { return i.avatar; })[0] || {}).id || (select && select.value ? parseInt(select.value, 10) : null));
      refreshMeta();
      if (data.can_edit) {
        VDH.sortable(grid, { items: ".vdh-card", handle: ".vdh-card-img", grid: true, onEnd: function () {
          var ids = Array.prototype.map.call(grid.querySelectorAll(".vdh-card"), function (c) { return c.dataset.id; });
          items.sort(function (a, b) { return ids.indexOf(String(a.id)) - ids.indexOf(String(b.id)); });
          if (count) count.textContent = "(đang lưu thứ tự…)";
          VDH.post(urls.order, { ids: ids.join(",") }).then(function (r) {
            refreshMeta();
            if (!r.ok && count) count.textContent = "(" + r.error + ")";
          });
        } });
      }
    }

    /* ---------------------------------------------------------- Tải ảnh */
    var wrap = document.getElementById("vdh-upload");
    if (!wrap) return;
    var zone = wrap.querySelector(".vdh-dropzone");
    var input = wrap.querySelector(".vdh-dz-input");
    var list = wrap.querySelector(".vdh-dz-list");
    var err = wrap.querySelector(".vdh-dz-error");
    var nguon = document.getElementById("vdh-up-nguon");
    var tacgia = document.getElementById("vdh-up-tacgia");
    try {
      nguon.value = localStorage.getItem("vdh-up-nguon") || "";
      tacgia.value = localStorage.getItem("vdh-up-tacgia") || "";
    } catch (e) { /* bỏ qua */ }
    var queue = [], running = 0;

    function showErr(m) { err.textContent = m; err.hidden = !m; }
    function ready() {
      if (!nguon.value.trim() || !tacgia.value.trim()) {
        showErr("Hãy nhập “Nguồn / bản quyền” và “Tác giả” trước khi tải ảnh (bắt buộc theo chuẩn ảnh).");
        (!nguon.value.trim() ? nguon : tacgia).focus();
        return false;
      }
      showErr("");
      try { localStorage.setItem("vdh-up-nguon", nguon.value.trim()); localStorage.setItem("vdh-up-tacgia", tacgia.value.trim()); } catch (e) { /* bỏ qua */ }
      return true;
    }
    function addFiles(files) {
      if (!files || !files.length) return;
      if (!ready()) return;
      Array.prototype.forEach.call(files, function (f) {
        var li = VDH.el("li", { "class": "vdh-up-item" });
        var name = VDH.el("span", { "class": "vdh-up-name" }, f.name + " · " + (f.size / 1048576).toFixed(1) + " MB");
        var bar = VDH.el("progress", { max: "100", value: "0" });
        var st = VDH.el("span", { "class": "vdh-up-state" }, "Đang chờ…");
        li.appendChild(name); li.appendChild(bar); li.appendChild(st);
        list.appendChild(li);
        if (!OK_EXT.test(f.name)) { fail(li, st, "Chỉ nhận JPG, PNG, WebP, HEIC."); return; }
        if (f.size > MAX) { fail(li, st, "Vượt 25 MB."); return; }
        queue.push({ file: f, li: li, bar: bar, st: st, nguon: nguon.value.trim(), tacgia: tacgia.value.trim() });
      });
      pump();
    }
    function fail(li, st, m) { li.classList.add("is-error"); st.textContent = m; }
    function pump() {
      while (running < 2 && queue.length) send(queue.shift());
    }
    function send(job) {
      running += 1;
      var fd = new FormData();
      fd.append("file", job.file);
      fd.append("nguon", job.nguon);
      fd.append("tac_gia", job.tacgia);
      var xhr = new XMLHttpRequest();
      xhr.open("POST", urls.upload);
      xhr.setRequestHeader("X-CSRFToken", VDH.csrf());
      xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
      job.st.textContent = "Đang tải…";
      xhr.upload.onprogress = function (e) {
        if (e.lengthComputable) {
          var p = Math.round(e.loaded / e.total * 100);
          job.bar.value = p;
          job.st.textContent = p < 100 ? ("Đang tải " + p + "%") : "Đang xử lý ảnh…";
        }
      };
      xhr.onload = function () {
        running -= 1;
        var r = null;
        try { r = JSON.parse(xhr.responseText); } catch (e) { r = { ok: false, error: "Lỗi máy chủ (" + xhr.status + ")." }; }
        if (xhr.status === 413) r = { ok: false, error: "Tệp quá lớn so với giới hạn máy chủ." };
        if (!r.ok) { job.bar.value = 0; fail(job.li, job.st, r.error || "Không tải được."); pump(); return; }
        job.bar.value = 100;
        job.li.classList.add("is-done");
        job.st.textContent = "Xong" + (r.warnings && r.warnings.length ? " – ⚠ " + r.warnings.join(" ") : "");
        if (r.warnings && r.warnings.length) job.li.classList.add("is-warn");
        var it = {
          id: r.id, thumb: r.thumb, large: r.large, width: r.width, height: r.height, chu_thich_vi: r.chu_thich_vi || "",
          chu_thich_en: "", chu_thich_zh_hans: "", tac_gia: r.tac_gia, nguon: r.nguon, la_minh_hoa: false,
          small: r.small, name: r.name
        };
        items.push(it);
        if (grid) {
          var c = card(it);
          c.classList.add("is-new");
          grid.appendChild(c);
        }
        if (select && !select.querySelector("option[value='" + r.id + "']")) select.appendChild(new Option("Ảnh #" + r.id + " – " + r.name, String(r.id)));
        if (r.avatar) setAvatarUI(r.id);
        refreshMeta();
        pump();
      };
      xhr.onerror = function () { running -= 1; fail(job.li, job.st, "Mất kết nối mạng."); pump(); };
      xhr.send(fd);
    }
    zone.addEventListener("click", function () { if (ready()) input.click(); });
    zone.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); if (ready()) input.click(); } });
    input.addEventListener("change", function () { addFiles(input.files); input.value = ""; });
    ["dragenter", "dragover"].forEach(function (ev) {
      zone.addEventListener(ev, function (e) { e.preventDefault(); zone.classList.add("is-over"); });
    });
    ["dragleave", "drop"].forEach(function (ev) {
      zone.addEventListener(ev, function (e) { e.preventDefault(); zone.classList.remove("is-over"); });
    });
    zone.addEventListener("drop", function (e) { addFiles(e.dataTransfer && e.dataTransfer.files); });
    // Thả nhầm ra ngoài khung không mở ảnh trong trình duyệt (mất dữ liệu đang soạn).
    window.addEventListener("dragover", function (e) { e.preventDefault(); });
    window.addEventListener("drop", function (e) { if (!zone.contains(e.target)) e.preventDefault(); });
  });
})();
