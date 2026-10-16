/* Trình soạn thảo trực quan cho textarea.vdh-richtext (Quill 2.0.3 tự host) – TR FR-A07.
 * Thanh công cụ tiếng Việt: Tiêu đề mục (h3), Tiêu đề nhỏ (h4), đậm, nghiêng, danh sách, danh sách số, trích dẫn,
 * liên kết, ảnh từ thư viện, xóa định dạng. Dán từ Word: chỉ giữ định dạng cơ bản.
 * Textarea gốc vẫn được gửi (HTML đồng bộ mỗi lần sửa); máy chủ làm sạch bằng bleach khi lưu.
 */
(function () {
  "use strict";
  if (!window.Quill) return;
  var VDH = window.VDH = window.VDH || {};
  if (VDH._richtext) return;
  VDH._richtext = true;
  var Delta = Quill.import("delta");
  var FORMATS = ["header", "bold", "italic", "list", "blockquote", "link", "image"];

  var TOOLBAR = [
    ["header", "3", "Tiêu đề mục", "Tiêu đề mục (ví dụ: Lịch sử)"],
    ["header", "4", "Tiêu đề nhỏ", "Tiêu đề nhỏ trong một mục"],
    ["|"],
    ["bold", "", "<b>Đ</b>", "Chữ đậm (Ctrl+B)"],
    ["italic", "", "<i>N</i>", "Chữ nghiêng (Ctrl+I)"],
    ["|"],
    ["list", "bullet", "• Danh sách", "Danh sách gạch đầu dòng"],
    ["list", "ordered", "1. Danh sách số", "Danh sách đánh số"],
    ["blockquote", "", "❝ Trích dẫn", "Đoạn trích dẫn"],
    ["|"],
    ["link", "", "Liên kết", "Chèn liên kết: bôi đen chữ rồi bấm"],
    ["image", "", "Ảnh từ thư viện", "Chèn ảnh đã tải lên thư viện"],
    ["|"],
    ["clean", "", "Xóa định dạng", "Xóa định dạng của đoạn đã bôi đen"]
  ];

  function buildToolbar() {
    var bar = document.createElement("div");
    bar.className = "vdh-rt-toolbar";
    var group = document.createElement("span");
    group.className = "ql-formats";
    bar.appendChild(group);
    TOOLBAR.forEach(function (t) {
      if (t[0] === "|") {
        group = document.createElement("span");
        group.className = "ql-formats";
        bar.appendChild(group);
        return;
      }
      var b = document.createElement("button");
      b.type = "button";
      b.className = "ql-" + t[0] + " vdh-rt-btn";
      if (t[1]) b.value = t[1];
      b.title = t[3];
      b.setAttribute("aria-label", t[3]);
      b.dataset.label = t[2];
      group.appendChild(b);
    });
    return bar;
  }

  /* ---- Dán từ Word: đổi h1/h2 thành Tiêu đề mục, h5/h6 thành Tiêu đề nhỏ, nhận danh sách kiểu Word ---- */
  function headingMatcher(level) {
    return function (node, delta) {
      return delta.compose(new Delta().retain(delta.length() - 1).retain(1, { header: level }));
    };
  }
  function wordListMatcher(node, delta) {
    var cls = node.getAttribute("class") || "";
    var style = node.getAttribute("style") || "";
    if (!/MsoList/i.test(cls) && !/mso-list/i.test(style)) return delta;
    var text = node.textContent.replace(/ /g, " ").trim();
    var ordered = /^(\d+|[a-zA-Z]|[ivxIVX]+)[.)]\s/.test(text);
    var ops = [];
    var stripped = false;
    delta.ops.forEach(function (op) {
      if (!stripped && typeof op.insert === "string") {
        var s = op.insert.replace(/^[\s ]*([·•▪◦§o\-–]|\d+[.)]|[a-zA-Z][.)]|[ivxIVX]+[.)])[\s ]+/, "");
        stripped = true;
        if (s) ops.push(Object.assign({}, op, { insert: s }));
      } else {
        ops.push(op);
      }
    });
    var d = new Delta(ops);
    return d.compose(new Delta().retain(d.length() - 1).retain(1, { list: ordered ? "ordered" : "bullet" }));
  }
  function ignoreMatcher() { return new Delta(); }
  function msoIgnoreMatcher(node, delta) {
    var style = node.getAttribute("style") || "";
    return /mso-list:\s*Ignore/i.test(style) ? new Delta() : delta;
  }

  function semanticHTML(q) {
    if (q.getLength() <= 1 && !q.root.querySelector("img")) return "";
    var html = typeof q.getSemanticHTML === "function" ? q.getSemanticHTML() : q.root.innerHTML;
    // Quill 2.0.x thay mọi dấu cách bằng &nbsp; trong getSemanticHTML – chuẩn hóa lại.
    html = html.replace(/&nbsp;/g, " ").replace(/ /g, " ");
    html = html.replace(/<p><br><\/p>/g, "").replace(/<p>\s*<\/p>/g, "");
    return html.trim();
  }

  /* ---- Hộp chọn ảnh từ thư viện ---- */
  var picker = null;
  function openPicker(ta, onPick) {
    if (!picker) {
      picker = document.createElement("div");
      picker.className = "vdh-modal";
      picker.hidden = true;
      picker.innerHTML =
        '<div class="vdh-modal-box" role="dialog" aria-modal="true" aria-labelledby="vdh-pick-title">' +
        '<div class="vdh-modal-head"><h2 id="vdh-pick-title">Chèn ảnh từ thư viện</h2>' +
        '<button type="button" class="vdh-modal-x" aria-label="Đóng">×</button></div>' +
        '<div class="vdh-pick-tools"><input type="search" class="vdh-pick-q" placeholder="Tìm theo chú thích, mã di tích…" form="vdh-noform">' +
        '<label class="vdh-pick-all"><input type="checkbox" form="vdh-noform"> Xem ảnh của mọi di tích</label></div>' +
        '<p class="vdh-pick-msg" role="status"></p><ul class="vdh-pick-grid"></ul>' +
        '<p class="vdh-pick-foot">Ảnh mới phải tải lên trước ở thẻ “Ảnh, video” của di tích (hoặc mục Thư viện ảnh).</p></div>';
      document.body.appendChild(picker);
      picker.addEventListener("click", function (e) {
        if (e.target === picker || e.target.closest(".vdh-modal-x")) close();
      });
      document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !picker.hidden) close(); });
    }
    var grid = picker.querySelector(".vdh-pick-grid");
    var msg = picker.querySelector(".vdh-pick-msg");
    var q = picker.querySelector(".vdh-pick-q");
    var all = picker.querySelector(".vdh-pick-all input");
    var scoped = ta.getAttribute("data-picker-url") || "";
    var global = ta.getAttribute("data-picker-all") || scoped;
    all.checked = scoped === global;
    all.parentNode.hidden = scoped === global;
    var timer = null;
    function close() { picker.hidden = true; document.body.classList.remove("vdh-modal-open"); }
    function load() {
      var base = all.checked ? global : scoped;
      var url = base + (base.indexOf("?") >= 0 ? "&" : "?") + "q=" + encodeURIComponent(q.value || "");
      msg.textContent = "Đang tải…";
      grid.innerHTML = "";
      fetch(url, { credentials: "same-origin" }).then(function (r) { return r.json(); }).then(function (data) {
        var items = data.items || [];
        msg.textContent = items.length ? "Bấm vào ảnh để chèn." :
          (all.checked ? "Không có ảnh phù hợp." : "Di tích này chưa có ảnh. Hãy tải ảnh ở thẻ “Ảnh, video” hoặc chọn “Xem ảnh của mọi di tích”.");
        items.forEach(function (it) {
          var li = document.createElement("li");
          var b = document.createElement("button");
          b.type = "button";
          b.className = "vdh-pick-item";
          var img = document.createElement("img");
          img.src = it.thumb; img.alt = ""; img.loading = "lazy";
          var cap = document.createElement("span");
          cap.textContent = (it.ditich ? it.ditich + " · " : "") + (it.caption || "(chưa có chú thích)") + (it.placeholder ? " · ảnh minh họa" : "");
          b.appendChild(img); b.appendChild(cap);
          b.addEventListener("click", function () { close(); onPick(it); });
          li.appendChild(b);
          grid.appendChild(li);
        });
      }).catch(function () { msg.textContent = "Không tải được thư viện ảnh."; });
    }
    q.oninput = function () { clearTimeout(timer); timer = setTimeout(load, 300); };
    all.onchange = load;
    picker.hidden = false;
    document.body.classList.add("vdh-modal-open");
    load();
    setTimeout(function () { q.focus(); }, 30);
  }

  function initOne(ta) {
    if (ta._quill || ta.closest(".empty-form")) return;
    var wrap = document.createElement("div");
    wrap.className = "vdh-rt";
    var toolbar = buildToolbar();
    var editor = document.createElement("div");
    editor.className = "vdh-rt-editor";
    wrap.appendChild(toolbar);
    wrap.appendChild(editor);
    ta.insertAdjacentElement("afterend", wrap);
    ta.classList.add("vdh-rt-source");
    ta.setAttribute("aria-hidden", "true");
    ta.tabIndex = -1;

    var q = new Quill(editor, {
      theme: "snow",
      formats: FORMATS,
      placeholder: ta.getAttribute("placeholder") || "Nhập nội dung…",
      modules: {
        toolbar: {
          container: toolbar,
          handlers: {
            image: function () {
              var range = q.getSelection(true);
              openPicker(ta, function (it) {
                var idx = range ? range.index : q.getLength();
                q.insertEmbed(idx, "image", it.url, "user");
                try { q.formatText(idx, 1, { alt: it.caption || "" }, "user"); } catch (e) { /* bỏ qua */ }
                q.setSelection(idx + 1, 0, "silent");
              });
            }
          }
        },
        clipboard: {
          matchers: [
            ["h1", headingMatcher(3)], ["h2", headingMatcher(3)],
            ["h5", headingMatcher(4)], ["h6", headingMatcher(4)],
            ["p", wordListMatcher], ["span", msoIgnoreMatcher],
            ["style", ignoreMatcher], ["meta", ignoreMatcher]
          ]
        }
      }
    });
    // Nhãn chữ tiếng Việt cho các nút (Quill tự chèn biểu tượng SVG).
    toolbar.querySelectorAll(".vdh-rt-btn").forEach(function (b) { b.innerHTML = b.dataset.label; });

    function load(html) {
      q.setContents(q.clipboard.convert({ html: html || "" }), "silent");
    }
    load(ta.value);
    q.history.clear();
    ta._quill = q;
    ta._vdhSetHtml = function (html) { ta.value = html; load(html); };
    var sync = function () { ta.value = semanticHTML(q); ta.dispatchEvent(new Event("vdh:change", { bubbles: true })); };
    q.on("text-change", sync);
    var form = ta.form || ta.closest("form");
    if (form) form.addEventListener("submit", function () { ta.value = semanticHTML(q); });
    if (ta.closest(".errors")) wrap.classList.add("vdh-rt-error");
    // Nhãn <label for=…> trỏ tới editor.
    if (ta.id) {
      var lab = document.querySelector("label[for='" + ta.id + "']");
      if (lab) lab.addEventListener("click", function (e) { e.preventDefault(); q.focus(); });
    }
  }

  VDH.initRichText = function (root) {
    (root || document).querySelectorAll("textarea.vdh-richtext").forEach(initOne);
  };

  VDH.ready = VDH.ready || function (fn) {
    if (document.readyState !== "loading") fn(); else document.addEventListener("DOMContentLoaded", fn);
  };
  VDH.ready(function () {
    VDH.initRichText();
    document.addEventListener("formset:added", function (e) { VDH.initRichText(e.target); });
  });
})();
