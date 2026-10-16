/* Khu quản trị Di tích Vân Đồn – tiện ích nhỏ, không phụ thuộc thư viện ngoài. */
(function () {
  "use strict";
  // Giao diện quản trị chỉ dùng chế độ sáng (đồng bộ với các trang Thống kê, Kiểm duyệt).
  document.documentElement.setAttribute("data-theme", "light");

  // Thanh menu bên trái mặc định thu gọn (trang chủ quản trị đã là menu chính) để bảng danh sách đủ rộng.
  // Người dùng bấm « / » để mở; Django ghi nhớ lựa chọn trong localStorage.
  try {
    if (window.localStorage.getItem("django.admin.navSidebarIsOpen") === null) {
      window.localStorage.setItem("django.admin.navSidebarIsOpen", "false");
    }
  } catch (e) { /* trình duyệt chặn localStorage: giữ mặc định của Django */ }

  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  ready(function () {
    // Nút In (trang hướng dẫn)
    document.querySelectorAll("[data-vd-print]").forEach(function (b) {
      b.addEventListener("click", function () { window.print(); });
    });

    // Ô nhập mã OTP: chỉ nhận số, tự gửi khi đủ 6 số
    document.querySelectorAll("input[data-vd-otp]").forEach(function (inp) {
      inp.addEventListener("input", function () {
        var v = inp.value.replace(/\D/g, "").slice(0, 6);
        if (inp.value !== v) inp.value = v;
        if (v.length === 6 && inp.hasAttribute("data-autosubmit") && inp.form && !inp.form.dataset.sent) {
          inp.form.dataset.sent = "1";
          inp.form.submit();
        }
      });
    });

    // Sao chép mã bí mật OTP
    document.querySelectorAll("[data-vd-copy]").forEach(function (b) {
      b.addEventListener("click", function () {
        var txt = b.getAttribute("data-vd-copy").replace(/\s/g, "");
        var done = function () {
          var old = b.textContent; b.textContent = "Đã sao chép";
          setTimeout(function () { b.textContent = old; }, 1600);
        };
        if (navigator.clipboard) navigator.clipboard.writeText(txt).then(done, function () {});
      });
    });

    // Hỏi lại trước các thao tác nhạy cảm
    document.querySelectorAll("form[data-vd-confirm]").forEach(function (f) {
      f.addEventListener("submit", function (e) {
        if (!window.confirm(f.getAttribute("data-vd-confirm"))) e.preventDefault();
      });
    });
  });
})();
