/* Vẽ biểu đồ trang Thống kê tương tác (Chart.js 4) */
(function () {
  "use strict";
  var C = { ngoc: "#0E6B6B", ngocDam: "#0A4A4E", son: "#A3302A", dong: "#B8893A", da: "#6F675B", muc: "#2B2620", vien: "#E3DACA" };
  var NHOM = [C.ngoc, C.dong, C.son, C.da, C.ngocDam];

  // Hiện/ẩn ô ngày khi chọn "Tùy chọn"
  var form = document.querySelector(".vd-filter");
  var ky = document.getElementById("vd-ky");
  function toggleRange() { if (form && ky) form.classList.toggle("is-custom", ky.value === "tuy_chon"); }
  if (ky) { ky.addEventListener("change", toggleRange); toggleRange(); }

  var el = document.getElementById("vd-data");
  if (!el || typeof Chart === "undefined") return;
  var D = JSON.parse(el.textContent);
  var dark = document.documentElement.dataset.theme === "dark" ||
    (document.documentElement.dataset.theme !== "light" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  var chu = dark ? "#B4AA98" : C.da, luoi = dark ? "#3b352d" : "#ECE5D6";
  var so = new Intl.NumberFormat("vi-VN");

  Chart.defaults.font.family = 'system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif';
  Chart.defaults.font.size = 12;
  Chart.defaults.color = chu;
  Chart.defaults.borderColor = luoi;
  Chart.defaults.plugins.legend.labels.boxWidth = 12;
  Chart.defaults.plugins.tooltip.callbacks.label = function (ctx) {
    var v = ctx.parsed[ctx.chart.options.indexAxis === "y" ? "x" : "y"];
    return " " + (ctx.dataset.label ? ctx.dataset.label + ": " : "") + so.format(v);
  };
  Chart.defaults.maintainAspectRatio = false;

  function trong(id, data) {
    var empty = !data || !data.length || data.every(function (v) { return !v; });
    if (empty) {
      var box = document.getElementById(id).parentNode;
      var p = document.createElement("div");
      p.className = "vd-empty-chart"; p.textContent = "Chưa có dữ liệu trong kỳ";
      box.appendChild(p);
    }
    return empty;
  }
  function ve(id, cfg) { var c = document.getElementById(id); if (c) new Chart(c, cfg); }
  var truc = { grid: { color: luoi }, ticks: { precision: 0, callback: function (v) { return so.format(v); } }, beginAtZero: true };
  var trucNhan = { grid: { display: false } };

  // (1) Đường: lượt xem + đánh giá (2 trục)
  if (!trong("c-chuoi", D.chuoi.luot_xem.concat(D.chuoi.danh_gia))) {
    ve("c-chuoi", {
      type: "line",
      data: { labels: D.chuoi.nhan, datasets: [
        { label: "Lượt xem", data: D.chuoi.luot_xem, borderColor: C.ngoc, backgroundColor: "rgba(14,107,107,.10)",
          fill: true, tension: .3, cubicInterpolationMode: "monotone", pointRadius: D.chuoi.nhan.length > 60 ? 0 : 2, yAxisID: "y" },
        { label: "Số đánh giá", data: D.chuoi.danh_gia, borderColor: C.son, backgroundColor: C.son,
          cubicInterpolationMode: "monotone", pointRadius: D.chuoi.nhan.length > 60 ? 0 : 2, borderWidth: 2, yAxisID: "y1" }
      ] },
      options: {
        interaction: { mode: "index", intersect: false },
        scales: {
          x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 14 } },
          y: Object.assign({}, truc, { title: { display: true, text: "Lượt xem" } }),
          y1: Object.assign({}, truc, { position: "right", grid: { display: false }, title: { display: true, text: "Đánh giá" } })
        },
        plugins: { legend: { position: "top", align: "end" } }
      }
    });
  }

  function ngang(id, rows, mau, label, max) {
    var data = rows.map(function (r) { return r.gia_tri; });
    if (trong(id, data)) return;
    ve(id, {
      type: "bar",
      data: { labels: rows.map(function (r) { return r.ma + " · " + (r.ten.length > 34 ? r.ten.slice(0, 33) + "…" : r.ten); }),
        datasets: [{ label: label, data: data, backgroundColor: mau, borderRadius: 3, barPercentage: .8 }] },
      options: {
        indexAxis: "y",
        scales: { x: Object.assign({}, truc, max ? { max: max, ticks: { stepSize: 1 } } : {}), y: { grid: { display: false }, ticks: { autoSkip: false, font: { size: 11 } } } },
        plugins: { legend: { display: false },
          tooltip: { callbacks: { label: function (ctx) {
            var r = rows[ctx.dataIndex];
            return " " + label + ": " + (max ? ctx.parsed.x.toFixed(2).replace(".", ",") + " (" + r.so + " đánh giá)" : so.format(ctx.parsed.x));
          } } } }
      }
    });
  }
  // (2) Top 10 lượt xem, (3) điểm TB top 15
  ngang("c-top-xem", D.top_luot_xem, C.ngoc, "Lượt xem");
  ngang("c-top-diem", D.top_diem, C.dong, "Điểm TB", 5);

  function chong(id, src, ngangChieu) {
    var all = [].concat.apply([], src.nhom.map(function (n) { return n.gia_tri; }));
    if (trong(id, all)) return;
    ve(id, {
      type: "bar",
      data: { labels: src.nhan, datasets: src.nhom.map(function (n, i) {
        return { label: n.nhan, data: n.gia_tri, backgroundColor: NHOM[i % NHOM.length], borderRadius: 2, barPercentage: .7 };
      }) },
      options: {
        indexAxis: ngangChieu ? "y" : "x",
        interaction: { mode: "index", intersect: false },
        scales: { x: Object.assign({}, ngangChieu ? truc : trucNhan, { stacked: true }),
                  y: Object.assign({}, ngangChieu ? trucNhan : truc, { stacked: true }) },
        plugins: { legend: { position: "bottom" } }
      }
    });
  }
  // (4) Phân bố sao (cột chồng), (5) góp ý theo loại (thanh chồng)
  chong("c-sao", D.phan_bo_sao, false);
  chong("c-gopy", D.gop_y_loai, true);

  // (6) Lượt xem theo ngôn ngữ / thiết bị
  function don(id, src, mau) {
    if (trong(id, src.gia_tri)) return;
    ve(id, {
      type: "bar",
      data: { labels: src.nhan, datasets: [{ label: "Lượt xem", data: src.gia_tri, backgroundColor: mau, borderRadius: 3, barPercentage: .6 }] },
      options: { indexAxis: "y", scales: { x: truc, y: trucNhan }, plugins: { legend: { display: false } } }
    });
  }
  don("c-ngon-ngu", D.theo_ngon_ngu, C.ngocDam);
  don("c-thiet-bi", D.theo_thiet_bi, C.dong);
})();
