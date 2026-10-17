/* Website di tích Vân Đồn – JavaScript dùng chung (không phụ thuộc thư viện). */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var I18N = window.VD_I18N || {};
  var t = function (k, d) { return I18N[k] || d; };

  // Menu & bộ lọc trên điện thoại
  $$("[data-toggle]").forEach(function (b) {
    b.addEventListener("click", function () {
      var el = document.getElementById(b.getAttribute("data-toggle"));
      var open = el.classList.toggle("open");
      b.setAttribute("aria-expanded", open ? "true" : "false");
    });
  });

  // Gợi ý tìm kiếm (FR-P04)
  $$("[data-suggest]").forEach(function (input) {
    var box = document.createElement("ul");
    box.className = "suggest"; box.hidden = true; box.setAttribute("role", "listbox");
    input.parentNode.appendChild(box);
    var timer, idx = -1;
    input.setAttribute("autocomplete", "off");
    input.addEventListener("input", function () {
      clearTimeout(timer);
      var q = input.value.trim();
      if (q.length < 2) { box.hidden = true; return; }
      timer = setTimeout(function () {
        fetch(input.getAttribute("data-suggest") + "?q=" + encodeURIComponent(q))
          .then(function (r) { return r.json(); })
          .then(function (d) {
            box.innerHTML = ""; idx = -1;
            d.items.forEach(function (it) {
              var li = document.createElement("li");
              var a = document.createElement("a");
              a.href = it.url;
              a.innerHTML = "<span></span><small></small>";
              a.firstChild.textContent = it.ten;
              a.lastChild.textContent = it.khu;
              li.appendChild(a); box.appendChild(li);
            });
            box.hidden = !d.items.length;
          })
          .catch(function () { box.hidden = true; });  // bản xem trước tĩnh không có API gợi ý
      }, 180);
    });
    input.addEventListener("keydown", function (e) {
      var items = $$("a", box);
      if (box.hidden || !items.length) return;
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        idx = (idx + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
        items.forEach(function (a, i) { a.classList.toggle("active", i === idx); });
      } else if (e.key === "Enter" && idx >= 0) { e.preventDefault(); location.href = items[idx].href; }
      else if (e.key === "Escape") { box.hidden = true; }
    });
    document.addEventListener("click", function (e) { if (!box.contains(e.target) && e.target !== input) box.hidden = true; });
  });

  // Bộ lọc tự gửi khi thay đổi
  // (trang danh sách/bản đồ có static/js/filter.js lọc ngay trên trình duyệt thì bỏ qua)
  $$("form[data-autosubmit]").forEach(function (f) {
    f.addEventListener("change", function (e) {
      if (f.hasAttribute("data-live")) return;
      if (e.target.matches("input[type=checkbox],select")) f.submit();
    });
  });

  // Thư viện ảnh – xem phóng to, vuốt trên điện thoại (FR-P05)
  var lb = $("#lightbox");
  if (lb) {
    var items = $$("[data-lb]"), cur = 0, img = $("img", lb), cap = $("p", lb), lastFocus;
    var show = function (i) {
      cur = (i + items.length) % items.length;
      img.src = items[cur].getAttribute("data-lb");
      img.alt = items[cur].getAttribute("data-cap") || "";
      cap.textContent = items[cur].getAttribute("data-cap") || "";
    };
    items.forEach(function (b, i) { b.addEventListener("click", function () { lastFocus = b; show(i); lb.classList.add("open"); $(".lb-close", lb).focus(); }); });
    var close = function () { lb.classList.remove("open"); if (lastFocus) lastFocus.focus(); };
    $(".lb-close", lb).addEventListener("click", close);
    $(".lb-prev", lb).addEventListener("click", function () { show(cur - 1); });
    $(".lb-next", lb).addEventListener("click", function () { show(cur + 1); });
    document.addEventListener("keydown", function (e) {
      if (!lb.classList.contains("open")) return;
      if (e.key === "Escape") close();
      if (e.key === "ArrowLeft") show(cur - 1);
      if (e.key === "ArrowRight") show(cur + 1);
    });
    var x0 = null;
    lb.addEventListener("touchstart", function (e) { x0 = e.touches[0].clientX; }, { passive: true });
    lb.addEventListener("touchend", function (e) {
      if (x0 === null) return;
      var dx = e.changedTouches[0].clientX - x0;
      if (Math.abs(dx) > 50) show(cur + (dx < 0 ? 1 : -1));
      x0 = null;
    });
  }

  // "Muốn đến" (FR-I04)
  $$("[data-want]").forEach(function (b) {
    var key = "vd_want_" + b.getAttribute("data-slug");
    try { if (localStorage.getItem(key)) b.setAttribute("aria-pressed", "true"); } catch (e) {}
    b.addEventListener("click", function () {
      if (b.getAttribute("aria-pressed") === "true") return;
      var csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || "";
      fetch(b.getAttribute("data-want"), { method: "POST", headers: { "X-CSRFToken": csrf }, credentials: "same-origin" })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          b.setAttribute("aria-pressed", "true");
          var c = $("[data-count]", b); if (c) c.textContent = d.count;
          try { localStorage.setItem(key, "1"); } catch (e) {}
        });
    });
  });

  // Sao chép liên kết
  $$("[data-copy]").forEach(function (b) {
    b.addEventListener("click", function () {
      var txt = b.getAttribute("data-copy");
      (navigator.clipboard ? navigator.clipboard.writeText(txt) : Promise.reject()).then(function () {
        var o = b.textContent; b.textContent = t("copied", "Đã sao chép"); setTimeout(function () { b.textContent = o; }, 1800);
      }).catch(function () { window.prompt("", txt); });
    });
  });

  // Sắp xếp "Gần tôi" khi không có filter.js (filter.js tự xử lý và đặt data-live)
  var sortSel = $("#sort");
  if (sortSel) sortSel.addEventListener("change", function () {
    if (sortSel.form.hasAttribute("data-live")) return;
    if (sortSel.value !== "gan") { sortSel.form.submit(); return; }
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(function (pos) {
      var f = sortSel.form;
      f.lat.value = pos.coords.latitude.toFixed(5); f.lng.value = pos.coords.longitude.toFixed(5); f.submit();
    }, function () { alert(t("geoFail", "Không lấy được vị trí. Hãy cho phép trình duyệt truy cập vị trí.")); });
  });
})();
