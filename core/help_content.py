"""Nội dung trang "Hướng dẫn sử dụng" trong khu quản trị (TR FR-H03, FR-H06).

Quản trị viên có thể sửa trực tiếp các bài này trong mục Hệ thống → Hướng dẫn sử dụng.
"""
from .models import HelpArticle

ARTICLES = [
    ("bat-dau", "1. Bắt đầu: đăng nhập, vai trò, xác thực 2 lớp", "Tài khoản, vai trò và bảo mật.", """
<h3>Vai trò</h3>
<ul>
<li><strong>Biên tập viên</strong>: thêm, sửa di tích, ảnh, video, tuyến, lễ hội, tin tức; gửi duyệt.</li>
<li><strong>Duyệt nội dung</strong>: như Biên tập viên, thêm quyền <em>Xuất bản / Ẩn</em> và xóa.</li>
<li><strong>Kiểm duyệt tương tác</strong>: duyệt nhận xét, xử lý góp ý, xem thống kê.</li>
<li><strong>Quản trị hệ thống</strong>: tài khoản, phân quyền, cấu hình, nhật ký.</li>
</ul>
<h3>Xác thực 2 lớp (bắt buộc với Quản trị hệ thống)</h3>
<ol>
<li>Cài ứng dụng <em>Google Authenticator</em> hoặc <em>Microsoft Authenticator</em> trên điện thoại.</li>
<li>Vào menu góc phải → <strong>Bật xác thực 2 lớp</strong>, quét mã QR.</li>
<li>Nhập 6 số đang hiện trên ứng dụng → <strong>Xác nhận</strong>.</li>
<li>Từ lần sau, sau khi nhập mật khẩu sẽ được hỏi mã 6 số.</li>
</ol>
<p><strong>Lưu ý:</strong> nhập sai mật khẩu 5 lần liên tiếp, tài khoản bị khóa 15 phút.</p>
"""),
    ("them-di-tich", "2. Thêm một di tích mới (5 bước)", "Trình hướng dẫn từng bước, khoảng 15 phút cho một di tích.", """
<p>Vào <strong>Bảng điều khiển → Thêm di tích (từng bước)</strong>. Trình hướng dẫn có 5 bước, có thể lưu nháp bất cứ lúc nào.</p>
<ol>
<li><strong>Thông tin chung</strong>: mã (ví dụ VD45), tên, cấp xếp hạng, loại hình, khu vực, địa chỉ mới.</li>
<li><strong>Vị trí</strong>: nhập tọa độ theo một trong 3 cách (xem bài 3). Di tích nhiều điểm: bấm <em>Thêm điểm</em>.</li>
<li><strong>Ảnh</strong>: kéo thả nhiều ảnh cùng lúc, chọn ảnh đại diện, ghi nguồn cho từng ảnh (xem bài 4).</li>
<li><strong>Nội dung</strong>: tóm tắt 1–3 câu (bắt buộc), bài giới thiệu chia mục, hướng dẫn tham quan.</li>
<li><strong>Kiểm tra và gửi duyệt</strong>: hệ thống liệt kê mục còn thiếu. Người có quyền Duyệt sẽ xuất bản.</li>
</ol>
<h3>Điều kiện để xuất bản</h3>
<p>Phải có: tên tiếng Việt, tóm tắt tiếng Việt, ảnh đại diện, cấp xếp hạng, khu vực. Bản tiếng Anh, tiếng Trung để trống thì trang công khai tự hiện bản tiếng Việt kèm nhãn "Bản dịch đang cập nhật".</p>
<h3>Bài giới thiệu nên có các mục</h3>
<p>Lịch sử; Giá trị; Kiến trúc, cảnh quan; Truyền thuyết, tín ngưỡng; Lễ hội. Dùng nút <em>Tiêu đề</em> trên thanh công cụ để tạo mục. Cuối bài ghi nguồn tham khảo ở mục <em>Nguồn tham khảo</em>.</p>
"""),
    ("toa-do", "3. Ba cách nhập tọa độ", "Dán độ-phút-giây, nhập thập phân hoặc chọn trên bản đồ.", """
<p>Ở thẻ <strong>Vị trí</strong> của di tích, mỗi điểm có một ô bản đồ. Ba cách sau tự đồng bộ với nhau:</p>
<h3>Cách 1 – Dán tọa độ độ-phút-giây (như trong danh mục)</h3>
<p>Dán nguyên chuỗi, ví dụ <code>20°53'49.3"N 107°18'33.7"E</code> vào ô <em>Tọa độ</em> → bấm <em>Đọc tọa độ</em>. Hệ thống tự đổi sang số thập phân và đặt điểm trên bản đồ.</p>
<h3>Cách 2 – Nhập số thập phân</h3>
<p>Ví dụ <code>20.897028, 107.309361</code> (vĩ độ trước, kinh độ sau, cách nhau dấu phẩy).</p>
<h3>Cách 3 – Chọn trực tiếp trên bản đồ</h3>
<ol>
<li>Gõ tên địa danh vào ô tìm kiếm trên bản đồ, hoặc kéo, thu phóng tới khu vực.</li>
<li>Bấm nút <em>Vệ tinh</em> để nhìn rõ mái đình, bến bãi.</li>
<li>Bấm vào đúng vị trí: điểm đỏ xuất hiện; có thể kéo điểm để chỉnh.</li>
</ol>
<h3>Lấy tọa độ tại hiện trường bằng điện thoại</h3>
<p>Mở Google Maps → giữ ngón tay tại vị trí đang đứng → dãy số hiện ở ô tìm kiếm → sao chép, dán vào hệ thống.</p>
<h3>Cảnh báo tự động</h3>
<ul><li>Tọa độ nằm ngoài phạm vi Vân Đồn.</li><li>Tọa độ trùng với điểm của di tích khác.</li></ul>
<p>Chọn <em>Độ tin cậy</em>: Đã xác minh thực địa / Theo danh mục / Vị trí tương đối / Chưa xác minh.</p>
"""),
    ("anh-video", "4. Tải ảnh, video và chuẩn ảnh", "Kéo thả nhiều ảnh, chuẩn kích thước, bản quyền.", """
<h3>Tải ảnh</h3>
<ol>
<li>Mở di tích → thẻ <strong>Ảnh, video</strong> → kéo thả nhiều ảnh vào khung (hoặc bấm <em>Chọn ảnh</em>).</li>
<li>Chờ thanh tiến trình chạy xong. Hệ thống tự xoay ảnh, xóa thông tin GPS trong ảnh, nén và tạo các cỡ nhỏ.</li>
<li>Kéo thả các ảnh để sắp thứ tự; bấm ngôi sao để chọn <strong>ảnh đại diện</strong>.</li>
<li>Nhập <strong>chú thích</strong> và <strong>nguồn / bản quyền</strong> cho từng ảnh (bắt buộc).</li>
</ol>
<h3>Chuẩn ảnh</h3>
<ul>
<li>Chiều ngang ≥ 1.920 px; ảnh bìa ≥ 2.400 px. Tỉ lệ 3:2 hoặc 16:9.</li>
<li>Ảnh rõ nét, đủ sáng; không chèn chữ, không logo đơn vị khác.</li>
<li>Định dạng JPG, PNG, WebP, HEIC (iPhone); tối đa 25 MB/ảnh.</li>
<li>Chỉ dùng ảnh của cơ quan hoặc ảnh đã được tác giả cho phép. Ảnh báo chí phải có văn bản đồng ý.</li>
</ul>
<h3>Ảnh từ liên kết ngoài</h3>
<p>Có thể dùng ảnh đang đăng trên trang khác mà không tải tệp về: mở <strong>Ảnh</strong> → <em>Thêm</em> → mục
<strong>Ảnh từ liên kết ngoài</strong>, dán địa chỉ ảnh (bắt đầu bằng https://) và địa chỉ trang bài viết chứa ảnh, ghi
<strong>nguồn</strong>. Trang công khai hiển thị dòng "Nguồn ảnh" dẫn về bài gốc. Ảnh chụp khu vực quanh di tích (không phải
chính di tích) phải ghi "(khu vực)" trong chú thích.</p>
<ul>
<li>Ảnh ngoài phụ thuộc trang nguồn: nếu trang nguồn xóa hoặc đổi địa chỉ, ảnh sẽ không hiện. Nên kiểm tra định kỳ.</li>
<li>Ảnh ngoài vẫn thuộc bản quyền của trang nguồn. Khi có ảnh của cơ quan hoặc ảnh đã được phép, tải ảnh lên thay thế,
chọn làm ảnh đại diện rồi xóa ảnh ngoài.</li>
</ul>
<h3>Ảnh minh họa tạm</h3>
<p>Ảnh có nhãn "ẢNH MINH HỌA – CHỜ ẢNH CHÍNH THỨC" do hệ thống tạo để giữ chỗ. Khi có ảnh thật: tải ảnh mới, chọn làm ảnh đại diện rồi xóa ảnh minh họa.</p>
<h3>Video</h3>
<p>Ưu tiên dán liên kết YouTube từ kênh chính thức (ví dụ kênh của Trung tâm Truyền thông tỉnh). Tệp MP4 tối đa 200 MB.</p>
"""),
    ("nhap-excel", "5. Nhập hàng loạt từ Excel", "Tải mẫu, điền, kiểm tra lỗi, xác nhận.", """
<ol>
<li>Vào <strong>Di tích → Nhập từ Excel</strong> → bấm <em>Tải file mẫu</em>.</li>
<li>Điền mỗi di tích một dòng (dòng 2 là ví dụ – xóa trước khi nhập). Cột tọa độ chấp nhận cả dạng độ-phút-giây và thập phân; nhiều điểm cách nhau dấu chấm phẩy <code>;</code> theo mẫu <em>Tên điểm: tọa độ</em>.</li>
<li>Tải file lên → hệ thống hiển thị bảng xem trước, đánh dấu lỗi từng dòng (thiếu trường, tọa độ sai, mã trùng).</li>
<li>Chọn <em>Thêm mới</em> hoặc <em>Cập nhật theo mã</em> → <strong>Xác nhận nhập</strong>. Dữ liệu chỉ được ghi sau bước này.</li>
</ol>
<p>Di tích nhập từ Excel ở trạng thái <em>Nháp</em>; cần thêm ảnh rồi gửi duyệt.</p>
"""),
    ("tuong-tac", "6. Duyệt nhận xét và xử lý góp ý", "Kiểm duyệt trước khi hiển thị; trả lời; mã tra cứu.", """
<h3>Nhận xét, đánh giá</h3>
<ol>
<li>Vào <strong>Thống kê → Kiểm duyệt nhanh</strong>.</li>
<li>Đọc từng thẻ. Thẻ có cờ đỏ là <em>nghi spam</em> (chứa liên kết, từ ngữ cấm…).</li>
<li>Bấm <strong>Duyệt</strong> (hiện công khai), <strong>Ẩn</strong> hoặc <strong>Spam</strong>. Có thể chọn nhiều thẻ và thao tác một lần.</li>
<li>Muốn trả lời: nhập vào ô <em>Phản hồi</em> → phản hồi hiện dưới nhận xét.</li>
</ol>
<p>Phím tắt: <kbd>j</kbd>/<kbd>k</kbd> chuyển thẻ, <kbd>a</kbd> duyệt, <kbd>h</kbd> ẩn, <kbd>s</kbd> spam.</p>
<h3>Góp ý, mong muốn</h3>
<ol>
<li>Vào <strong>Tương tác người dùng → Góp ý, mong muốn</strong>; lọc theo loại, trạng thái.</li>
<li>Mở góp ý → chọn <em>Người xử lý</em>, đổi <em>Trạng thái</em> (Mới → Đang xử lý → Đã xử lý / Đóng), ghi chú nội bộ.</li>
<li>Nhập <em>Phản hồi cho người gửi</em>. Người gửi dùng <strong>mã tra cứu</strong> (ví dụ GY-2026-00012) để xem phản hồi trên website.</li>
<li>Câu hỏi hay có thể đánh dấu <em>Công khai trong mục Hỏi đáp</em>.</li>
</ol>
<p>Góp ý loại <strong>Báo di tích xuống cấp</strong> được gửi email ngay cho địa chỉ trong Cấu hình hệ thống.</p>
"""),
    ("bao-cao", "7. Thống kê và xuất báo cáo Excel", "Dashboard, bộ lọc, xuất Excel có biểu đồ.", """
<ol>
<li>Vào <strong>Thống kê</strong>. Chọn kỳ (7 ngày, 30 ngày, quý, năm hoặc tùy chọn), di tích, khu vực, cấp, ngôn ngữ.</li>
<li>Xem các chỉ số và biểu đồ; mỗi chỉ số có so sánh với kỳ trước.</li>
<li>Bấm <strong>Xuất Excel</strong>: file gồm Tổng quan (có biểu đồ), Theo di tích, Đánh giá chi tiết, Góp ý chi tiết, Lượt xem theo ngày. Biểu đồ là biểu đồ Excel gốc, có thể sửa màu, tiêu đề.</li>
</ol>
<p>Email, số điện thoại người dùng trong báo cáo được che một phần để bảo vệ dữ liệu cá nhân.</p>
"""),
    ("van-hanh", "8. Vận hành: cấu hình, sao lưu, khóa bản đồ", "Dành cho Quản trị hệ thống.", """
<h3>Cấu hình hệ thống</h3>
<p>Mục <strong>Hệ thống → Cấu hình hệ thống</strong>: Google Maps API key, thông tin liên hệ ở chân trang, email nhận thông báo, ngưỡng cảnh báo nhận xét chờ duyệt, liên kết mạng xã hội.</p>
<h3>Google Maps API key</h3>
<ol>
<li>Đăng nhập Google Cloud Console bằng tài khoản của cơ quan → tạo dự án.</li>
<li>Bật <em>Maps JavaScript API</em>, <em>Maps Embed API</em>, <em>Places API</em> (ô tìm địa danh khi chọn tọa độ).</li>
<li>Tạo API key → giới hạn theo tên miền website (HTTP referrers) và chỉ 3 API trên.</li>
<li>Đặt hạn mức (quota) và cảnh báo ngân sách để tránh phát sinh chi phí.</li>
<li>Dán khóa vào Cấu hình hệ thống. Khi chưa có khóa, website tự dùng bản đồ OpenStreetMap.</li>
</ol>
<h3>Sao lưu</h3>
<p>Hệ thống tự sao lưu cơ sở dữ liệu hằng ngày (giữ 30 bản) và ảnh hằng tuần. Hướng dẫn phục hồi trong tài liệu vận hành (README triển khai).</p>
<h3>Nhật ký thao tác</h3>
<p>Mục <strong>Hệ thống → Nhật ký thao tác</strong> ghi mọi thao tác tạo, sửa, xóa, xuất bản, duyệt, đăng nhập.</p>
"""),
]


def load_help(update=False):
    for i, (slug, title, summary, body) in enumerate(ARTICLES):
        obj = HelpArticle.objects.filter(slug=slug).first()
        if obj and not update:
            continue
        obj = obj or HelpArticle(slug=slug)
        obj.title, obj.summary, obj.body, obj.order = title, summary, body.strip(), i
        obj.save()
