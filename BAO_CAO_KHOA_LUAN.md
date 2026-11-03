# BÁO CÁO KHÓA LUẬN TỐT NGHIỆP

## HỆ THỐNG GIÁM SÁT NGƯỜI CAO TUỔI TRONG NHÀ THÔNG MINH
### SỬ DỤNG WIFI FINGERPRINTING VÀ CẢM BIẾN CHUYỂN ĐỘNG

---

**Sinh viên:** Nguyễn Hoài Phúc  
**MSSV:** 2001230687  
**Ngành:** Công nghệ Thông tin - KLCN 336  
**Giảng viên hướng dẫn:** ……………………………… *(điền tên GVHD)*
**Năm học:** 2026–2027
**Ngày nộp:** 01/11/2026  

---

## MỤC LỤC

1. [Mở đầu](#1-mở-đầu)
2. [Tổng quan hệ thống](#2-tổng-quan-hệ-thống)
3. [Cơ sở lý thuyết](#3-cơ-sở-lý-thuyết)
4. [Thiết kế hệ thống](#4-thiết-kế-hệ-thống)
5. [Triển khai phần cứng](#5-triển-khai-phần-cứng)
6. [Phát triển phần mềm](#6-phát-triển-phần-mềm)
7. [Bảo mật hệ thống](#7-bảo-mật-hệ-thống)
8. [Kiểm thử và đánh giá](#8-kiểm-thử-và-đánh-giá)
9. [Triển khai thực tế](#9-triển-khai-thực-tế)
10. [Kết luận và hướng phát triển](#10-kết-luận-và-hướng-phát-triển)
11. [Tài liệu tham khảo](#11-tài-liệu-tham-khảo)
12. [Phụ lục](#12-phụ-lục)

---

## 1. MỞ ĐẦU

### 1.1. Bối cảnh và động lực

Dân số già hóa là thách thức chung của nhiều quốc gia, trong đó có Việt Nam. Theo số liệu công bố của Tổng cục Thống kê, nhóm người từ 60 tuổi trở lên chiếm khoảng 12% dân số Việt Nam trong giai đoạn 2023; các dự báo dân số cho thấy tỷ lệ này có thể đạt khoảng 25% vào năm 2050. Với xu hướng gia đình hạt nhân, nhiều người cao tuổi sống một mình hoặc ở cùng người thân cũng đã đi làm cả ngày. Việc theo dõi sức khỏe, phát hiện sớm các sự cố như ngã, bất thường hoạt động trở nên cấp thiết.

Các giải pháp hiện có chủ yếu dựa trên camera giám sát hoặc thiết bị đeo tay. Camera vi phạm quyền riêng tư, đắt đỏ khi lắp đặt nhiều phòng. Thiết bị đeo tay dễ bị người cao tuổi quên mang, mất pin, hoặc gây khó chịu khi ngủ. Cần một giải pháp **phi xâm nhập, giá thành thấp, không cần tương tác chủ động từ người được giám sát**.

### 1.2. Mục tiêu đề tài

Xây dựng hệ thống giám sát người cao tuổi trong nhà thông minh với các yêu cầu:

- **Định vị mức phòng** (room-level localization) bằng WiFi fingerprinting - không cần thiết bị đeo
- **Phát hiện bất thường** hoạt động hàng ngày (ngã, bất động quá lâu, thay đổi thói quen)
- **Phát hiện ngã** bằng cảm biến gia tốc kế trên điện thoại (tùy chọn)
- **Cảnh báo thời gian thực** qua web dashboard và webhook (Telegram, ntfy.sh, IFTTT)
- **Bảo mật dữ liệu** - mã hóa, xác thực, rate limiting, certificate pinning
- **Triển khai dễ dàng** - Docker, auto-discovery qua NSD, HTTPS tự động

### 1.3. Phạm vi và giới hạn

- Hệ thống hoạt động trong môi trường nhà có WiFi ổn định (tối thiểu 3 AP nghe được)
- Độ chính xác định vị phòng: mục tiêu > 85% trên tập test
- Phát hiện ngã: chỉ hoạt động khi người cao tuổi mang điện thoại (tùy chọn)
- Không thay thế thiết bị y tế chuyên dụng - chỉ là hỗ trợ cảnh báo sớm

### 1.4. Nghiên cứu liên quan

**Định vị trong nhà bằng WiFi.** Hướng tiếp cận này bắt đầu từ RADAR [2], nơi vị trí được suy ra
từ vector cường độ tín hiệu thu (RSSI) của nhiều access point và đối chiếu với một cơ sở dữ liệu
fingerprint đã đo trước. RADAR dùng k-nearest neighbours trên khoảng cách Euclid và trả về toạ độ
liên tục trong mặt bằng. Các công trình sau đó chuyển sang mô hình xác suất (Horus) và học sâu
(DeepFi, CiFi), chủ yếu để tăng độ chính xác ở mức toạ độ. Khóa luận này đặt bài toán ở **mức
phòng** chứ không phải toạ độ: đầu ra là một nhãn rời rạc trong danh sách phòng của căn nhà. Cách
đặt vấn đề đó biến bài toán thành phân loại nhiều lớp thay vì hồi quy, và phù hợp với nhu cầu thực
tế của gia đình — biết người thân đang ở phòng nào là đủ để phát hiện bất thường, không cần biết
chính xác đang đứng ở mét thứ mấy.

**Học đa nhiệm trên fingerprint WiFi.** ARIL [3] là công trình gần với khóa luận nhất: một bộ mã
hoá dùng chung cho hai đầu ra là hoạt động và vị trí, với lập luận rằng hai bài toán bổ trợ cho
nhau. Khóa luận áp dụng đúng ý tưởng đó cho lớp `RoomNetMT`: một encoder chung, hai head (phòng và
hoạt động bốn lớp). Khác biệt nằm ở chỗ ARIL dùng dữ liệu CSI còn khóa luận dùng RSSI — lựa chọn
này xuất phát từ ràng buộc thiết bị, trình bày ở mục 1.5.

**Tín hiệu WiFi cho nhận diện hoạt động.** Ngoài vị trí, sự biến thiên RSSI giữa các lần quét mang
thông tin về mức độ chuyển động trong phòng. Các nghiên cứu về WiFi sensing khai thác điều này để
phân loại hoạt động. Khóa luận dùng một biến thể đơn giản hơn: độ lệch RSSI trung vị giữa các cửa
sổ, phân thành bốn mức (đứng yên, hoạt động nhẹ, đang di chuyển, vừa chuyển phòng). Cách này không
cần dữ liệu gán nhãn hoạt động, mà suy nhãn từ chính bộ luật phát hiện bất thường.

**Phát hiện bất thường cho người cao tuổi.** Hướng phổ biến là học phân bố của chuỗi hoạt động
bình thường rồi đánh dấu những chuỗi lệch khỏi phân bố đó. Autoencoder hồi tiếp (GRU-AE) là lựa
chọn thường gặp vì không cần dữ liệu bất thường khi huấn luyện. Khóa luận dùng GRU-AE để tính sai
số tái tạo, nhưng kết hợp thêm một bộ luật tường minh (lưu trú quá lâu, chuyển phòng không hợp
`room_topology`, di chuyển ban đêm). Kết quả ở mục 8 cho thấy phần lớn tín hiệu cảnh báo đến từ bộ
luật; GRU-AE đóng góp ở nhóm bất thường về quỹ đạo. Việc tách bạch hai nguồn này quan trọng cho
phần đánh giá, vì nếu gộp lại thì không biết mô hình học được gì.

**Phát hiện ngã.** Các hệ thống thương mại thường dùng thiết bị đeo với gia tốc kế và con quay.
Khóa luận không làm thiết bị đeo; phần phát hiện ngã dùng cảm biến của điện thoại và chỉ hoạt động
khi điện thoại đang mở ứng dụng. Đây là hạn chế đã biết và được ghi rõ ở mục 8.4, không được tính
là kết quả đã kiểm chứng.

### 1.5. Đối chiếu với các dự án mã nguồn mở

Với các thành phần chưa có kinh nghiệm, khóa luận đọc mã nguồn của dự án đang dùng rộng rãi để đối
chiếu cách làm trước khi tự viết, thay vì bắt đầu từ con số không.

| Dự án | Lấy gì | Không lấy gì |
|---|---|---|
| **FIND3** (`schollz/find3`) | Quy trình tách hai pha *learn* và *track*, và ý tưởng dùng một meta-model chọn mô hình tốt nhất theo từng vị trí | Kiến trúc dịch vụ và cơ chế đồng bộ nhiều server của FIND3 — quá nặng cho phạm vi một căn nhà |
| **ARIL** (`geekfeiw/ARIL`) | Cấu trúc encoder dùng chung cho hai head (vị trí và hoạt động) | Đầu vào CSI; khóa luận chỉ có RSSI |
| **Home Assistant** | Cách tổ chức thực thể theo nhà và cách phát cảnh báo ra ngoài | Toàn bộ mô hình tích hợp thiết bị — khóa luận chỉ cần WiFi và điện thoại |
| **ntfy.sh** | Giao thức đẩy cảnh báo đơn giản qua HTTP POST | Không tự viết lại; dùng nguyên dịch vụ |
| **OWASP Top 10** | Danh mục kiểm tra cho phần bảo mật | Không áp nguyên si; chọn các mục liên quan tới ứng dụng chạy trong LAN |

Việc đối chiếu này dẫn tới hai quyết định thiết kế. Thứ nhất, **dùng RSSI thay vì CSI**: đọc CSI cần
phần cứng đặc thù (ESP32 có công cụ riêng) hoặc quyền root trên điện thoại, trong khi RSSI đọc được
từ bất kỳ điện thoại Android nào và từ router. Đổi lại độ chính xác thấp hơn, được bù bằng việc chỉ
yêu cầu độ phân giải mức phòng. Thứ hai, **tự chứa thay vì phụ thuộc dịch vụ đám mây**: dữ liệu vị
trí là dữ liệu riêng tư, nên toàn bộ suy luận chạy trên máy chủ trong nhà; chỉ cảnh báo mới được
đẩy ra ngoài, và chỉ khi chủ nhà tự cấu hình webhook.

Cần nói rõ để tránh hiểu nhầm về đóng góp: các mô hình học máy trong khóa luận đều dựa trên công
trình đã công bố, không có kiến trúc nào do khóa luận phát minh. Phần làm mới nằm ở việc ghép chúng
thành một hệ thống chạy được trên thiết bị phổ thông, ở cách đánh giá tách bạch (mục 8), và ở các
lớp kỹ thuật phục vụ vận hành thực tế (mục 7 và 9).

### 1.6. Phương pháp thực hiện

Khóa luận đi theo trình tự sau, mỗi bước đều để lại kết quả kiểm chứng được:

1. **Khảo sát yêu cầu** từ đề cương chi tiết của học phần, chuyển thành danh sách chức năng và chỉ
   tiêu đo được (định vị trên 85% ở tập test, cảnh báo trong vòng vài giây).
2. **Thu thập và chuẩn hoá dữ liệu.** Bộ dữ liệu tổng hợp được dựng theo bố cục căn hộ hai phòng
   ngủ và một hành lang, có nhiễu thiết bị và hiện tượng mất tín hiệu; phiên bản hai được làm khó
   hơn sau khi phát hiện phiên bản đầu quá dễ (xem mục 8.2). Dữ liệu được chia theo *phiên* thu,
   không chia theo mẫu, để tránh rò rỉ thông tin giữa các tập.
3. **Huấn luyện và đánh giá mô hình.** Ba mô hình định vị được so sánh trên cùng một cách chia tập;
   kết quả được lưu thành JSON trong `results/` để mọi số liệu trong báo cáo truy được về nguồn.
4. **Xây dựng hệ thống.** Flask và SQLite ở phía máy chủ, PWA cho giao diện, ứng dụng Android cho
   phần thu thập, và các blueprint tách theo miền chức năng.
5. **Soát bảo mật.** Đối chiếu với OWASP Top 10 ở phần liên quan, kiểm tra bằng script quét phân
   quyền và script quét mã, ghi lại từng lỗi và cách sửa.
6. **Đóng gói và kiểm chứng triển khai.** Docker đa tầng, gunicorn, hai phương án đưa ra Internet
   (Cloudflare Tunnel hoặc VPS kèm chứng chỉ), và chạy thử để xác nhận cấu hình hoạt động.

Nguyên tắc xuyên suốt: **không ghi vào báo cáo con số nào chưa chạy ra**. Kết quả nào chưa đo được
thì ghi rõ là chưa kiểm thử, ví dụ phần phát hiện ngã ở mục 8.4.

### 1.7. Đóng góp của khóa luận

- Một hệ thống hoàn chỉnh chạy được từ đầu tới cuối: thu fingerprint, huấn luyện, suy luận thời
  gian thực, cảnh báo, và giao diện quản trị nhiều căn nhà.
- Lớp `RoomNetMT` học đa nhiệm trên RSSI, dùng encoder chung cho vị trí và hoạt động, với nhãn hoạt
  động được suy tự động từ bộ luật thay vì cần dữ liệu gán nhãn thủ công.
- Quy trình đánh giá tách bạch: ba tập train/validation/test chia theo phiên, K-fold, và các
  baseline cổ điển (kNN, Random Forest, MLP, SimpleCNN) để so sánh.
- Các lớp kỹ thuật phục vụ vận hành: phân quyền theo nhà và theo vai trò, hạn mức tần suất lưu trong
  RAM hoặc Redis tuỳ quy mô triển khai, và bộ kiểm tra bảo mật chạy lại được.
- Bộ công cụ triển khai: Docker Compose nhiều service, hai đường ra Internet, và tài liệu vận hành
  kèm bảng xử lý sự cố.

### 1.8. Cấu trúc báo cáo

Mục 2 trình bày kiến trúc tổng thể và luồng dữ liệu. Mục 3 là cơ sở lý thuyết của ba mô hình dùng
trong hệ thống. Mục 4 mô tả thiết kế qua các sơ đồ use case, sequence, class, state và deployment.
Mục 5 nói về phần cứng tối thiểu và cách bố trí access point. Mục 6 là phần phát triển phần mềm,
chi tiết nhất vì chiếm phần lớn khối lượng công việc. Mục 7 trình bày các lớp bảo mật cùng lý do
lựa chọn. Mục 8 là kết quả đo được, kèm cả những phần chưa kiểm thử. Mục 9 hướng dẫn triển khai.
Mục 10 tổng kết và nêu hướng phát triển. Phần phụ lục gom các thao tác cài đặt và tra cứu nhanh.

---

## 2. TỔNG QUAN HỆ THỐNG

### 2.1. Kiến trúc tổng thể

```
┌─────────────────┐     WiFi/HTTP      ┌─────────────────┐
│  Android App    │ ◄─────────────────► │  Flask Server   │
│  (Collector)    │   Scan + Sensor     │  (Inference)    │
└─────────────────┘                     └────────┬────────┘
                                                 │
                    ┌────────────────────────────┼────────────────────────────┐
                    ▼                            ▼                            ▼
             ┌──────────────┐           ┌────────────────┐           ┌──────────────┐
             │  SQLite DB   │           │  PyTorch Model │           │  Webhooks    │
             │  (Persistent)│           │  (RoomNet-Lite)│           │ (Telegram/   │
             └──────────────┘           └────────────────┘           │  ntfy/IFTTT) │
                                                                    └──────────────┘
```

### 2.2. Các thành phần chính

| Thành phần | Công nghệ | Chức năng |
|------------|-----------|-----------|
| **Android Collector** | Kotlin, NSD, Sensor API | Quét WiFi, đọc gia tốc kế, gửi dữ liệu |
| **Flask Server** | Python 3.11, Flask, Gunicorn | API REST, WebSocket/SSE, Web dashboard |
| **Inference Engine** | PyTorch, RoomNet-Lite, GRU-AE | Định vị phòng, phát hiện bất thường |
| **Database** | SQLite (WAL mode) | Lưu fingerprint, prediction, alert, device |
| **Web Dashboard** | HTML5, JS ES6, CSS Grid, PWA | Real-time monitoring, cấu hình, báo cáo |
| **Android NSD** | NsdManager | Auto-discover server IP trong LAN |

### 2.3. Luồng dữ liệu chính

1. **Thu thập fingerprint (Offline/Training):** Android app quét WiFi tại phòng xác định → gửi lên server gán nhãn phòng → lưu vào DB
2. **Huấn luyện:** Server đọc fingerprint từ DB → train RoomNet-Lite (classification) + GRU-AE (anomaly) → lưu model `.pt`
3. **Giám sát realtime (Online):** Android app quét WiFi định kỳ (5s/lần) + đọc gia tốc kế → gửi server → inference realtime → cập nhật dashboard
4. **Cảnh báo:** Phát hiện bất thường/ngã → lưu alert DB → đẩy webhook (nếu cấu hình) → hiển thị dashboard

---

## 3. CƠ SỞ LÝ THUYẾT

### 3.1. WiFi Fingerprinting

Cường độ tín hiệu nhận được tại một điểm phụ thuộc vào khoảng cách tới access point và vào cách
sóng phản xạ trên tường, đồ đạc, cơ thể người. Trong không gian trong nhà, tia trực tiếp thường yếu
hoặc không tồn tại; tín hiệu thu được là tổng của nhiều tia phản xạ khác pha. Chính hiện tượng đa
đường này làm cho mức tín hiệu tại mỗi chỗ trong nhà có một tổ hợp giá trị khá ổn định theo từng
access point. Tổ hợp đó được gọi là fingerprint, và bài toán định vị trở thành bài toán so khớp một
vector đo được với các vector đã đo trước.

Mỗi fingerprint là một vector có số chiều bằng số access point quan sát được; phần tử thứ *i* là
mức RSSI nhận từ AP thứ *i*, tính bằng dBm. Giá trị này luôn âm và càng gần 0 thì tín hiệu càng
mạnh; trong thực tế thường nằm giữa −90 dBm và −30 dBm.

**Vì sao chọn RSSI mà không dùng CSI.** Chỉ số trạng thái kênh (CSI) chứa nhiều thông tin hơn vì giữ
được cả biên độ và pha của từng sóng con. Đổi lại, đọc CSI cần phần cứng đặc thù hoặc quyền root
trên điện thoại. RSSI thì bất kỳ điện thoại Android nào cũng đọc được ở chế độ người dùng thường,
và nhiều router cũng cung cấp. Khóa luận chấp nhận mất mát về lượng thông tin để đổi lấy khả năng
chạy trên thiết bị phổ thông — điều kiện để hệ thống có thể dùng trong nhà mà không cần đầu tư thêm.

**Vì sao chọn mức phòng.** Ở mức toạ độ liên tục, sai số vài mét là bình thường và việc đánh giá
phức tạp hơn nhiều. Ở mức phòng, đầu ra là một nhãn rời rạc trong danh sách phòng của căn nhà, nên
sai số trở thành một quyết định đúng hoặc sai, dễ đo và dễ giải thích cho người dùng. Với mục tiêu
phát hiện bất thường sinh hoạt, biết người thân đang ở phòng nào là đủ.

**Nguồn nhiễu và cách xử lý.** Mức RSSI dao động do người đi lại, cửa đóng mở, và cả do hướng cầm
điện thoại. Bốn biện pháp được dùng trong hệ thống:

- *Cửa sổ trượt* gộp 5 mẫu liên tiếp (tham số `data.window_size`) để làm phẳng dao động nhanh. Cửa
  sổ ngắn hơn thì phản ứng nhanh nhưng nhiễu hơn; 5 mẫu là mức cân bằng chọn theo thực nghiệm.
- *Tăng cường dữ liệu* khi huấn luyện: thêm nhiễu Gauss và ngẫu nhiên bỏ một số access point, mô
  phỏng tình huống AP không nghe thấy. Nếu không làm bước này, mô hình học thuộc đúng bộ AP của
  ngày thu dữ liệu và giảm độ chính xác khi mang sang thiết bị khác.
- *Giá trị thay thế cho AP bị mất* là −100 dBm (tham số `data.missing_rssi`), không dùng 0. Nếu dùng
  0, mô hình hiểu nhầm đó là tín hiệu cực mạnh, trong khi ý nghĩa thật là "không nghe thấy".
- *Băm BSSID* trước khi dùng làm tên chiều. Có hai lý do. Thứ nhất, địa chỉ MAC thô của access point
  là dữ liệu có thể dùng để suy ra vị trí, không nên lưu nguyên. Thứ hai, cùng một access point
  nhưng công cụ trên máy tính trả về chữ hoa còn Android trả về chữ thường; nếu không chuẩn hoá, hệ
  thống coi chúng là hai AP khác nhau và fingerprint bị lệch giữa hai nguồn thu. Đây là lỗi có thật
  đã gặp trong quá trình làm và được xử lý bằng cách viết thường địa chỉ trước khi băm.

### 3.2. Mô hình RoomNet-Lite (Phân loại phòng)

Kiến trúc CNN 1D nhẹ cho dữ liệu chuỗi RSSI:

```
Input: [Batch, Channels=AP_count, Seq_len=Window_size]
├── Conv1D(32, kernel=3) + BN + ReLU + Dropout(0.15)
├── Conv1D(64, kernel=3) + BN + ReLU + Dropout(0.15)
├── GlobalAvgPool1D
├── FC(Embedding=64) + Center Loss (λ=0.02)
└── FC(Num_rooms) + Softmax
```

**Loss function:** `L = L_CE + λ_center * L_center + λ_temporal * L_temporal`

- `L_CE`: Cross-entropy chuẩn
- `L_center`: Kéo embedding cùng lớp về gần nhau (Wen et al., 2016)
- `L_temporal`: Tính liên tục giữa các dự đoán liên tiếp (smooth transition)

**Vì sao dùng tích chập một chiều trên trục access point.** Vector RSSI không có thứ tự không gian —
AP thứ ba không "gần" AP thứ tư theo nghĩa vật lý. Tuy vậy, một lớp tích chập một chiều vẫn hữu ích
vì nó học được sự xuất hiện đồng thời của các nhóm AP: ở một phòng nào đó thường có ba AP mạnh và
hai AP yếu, và mẫu đó lặp lại. Tích chập một chiều rẻ hơn nhiều so với mạng đầy đủ có cùng số tham
số, và giữ được tính bất biến với thứ tự các AP trong danh sách.

**Vì sao tích chập tách rời theo chiều sâu.** Bản đầy đủ của RoomNet-Lite dùng tích chập tách rời
(depthwise separable) thay cho tích chập thường: mỗi kênh được lọc riêng rồi mới trộn kênh bằng một
tích chập điểm. Cách này giảm mạnh số tham số mà gần như giữ nguyên chất lượng, và đây là lý do mô
hình chạy được suy luận nhanh trên máy chủ yếu (số đo ở mục 8.5).

**Hai hàm mất mát phụ.** Cross-entropy một mình chỉ quan tâm tới việc đoán đúng nhãn, không quan tâm
các mẫu cùng phòng có nằm gần nhau trong không gian embedding hay không. CenterLoss thêm một số hạng
`L_center = ½ · Σ ‖x_i − c_{y_i}‖²` để kéo embedding của mọi mẫu cùng phòng về tâm của phòng đó.
Việc này quan trọng cho các bước sau: bộ lọc topology và bộ làm mượt đều làm việc trên phân bố xác
suất, nên nếu các lớp chồng lên nhau thì các bước đó không còn nhiều tác dụng.

Hàm mất mát thứ hai xử lý tính liên tục theo thời gian. Trong nhà, người không thể nhảy từ phòng ngủ
sang nhà bếp rồi quay lại trong hai giây. Số hạng `L_temporal` đo độ lệch Jensen–Shannon giữa phân bố
xác suất của hai lần suy luận liên tiếp và phạt những chỗ đổi đột ngột. Trọng số của hai số hạng phụ
nằm trong `config.yaml` (`center_loss_weight`, `temporal_loss_weight`) và được chọn trên tập
validation, không dùng tập test.

### 3.3. GRU Autoencoder (Phát hiện bất thường)

Mô hình sequence-to-sequence học biểu diễn bình thường của chuỗi hoạt động:

```
Encoder: GRU(48) → Latent(24)
Decoder: GRU(48) → Reconstruction
Loss: MSE(reconstruction) + λ_room * CE(room) + λ_cont * L_continuous
```

Ngưỡng bất thường: Quantile 0.99 trên reconstruction error của tập validation. Phát hiện: reconstruction error > ngưỡng VÀ chuyển phòng bất thường theo topology.

**Đầu vào của mô hình.** Mỗi bước thời gian được biểu diễn bằng một vector đặc trưng hành vi gồm ba
phần: phòng đang ở dưới dạng one-hot, thời gian lưu trú đã chuẩn hoá theo ngưỡng cảnh báo của phòng
đó, và một cờ cho biết bước này có chuyển phòng hay không. Một chuỗi dài 8 bước
(`data.anomaly_sequence_length`) được đưa vào mô hình. Cách biểu diễn này bỏ hẳn phần RSSI thô vì
bài toán ở đây là phát hiện *kiểu sinh hoạt* bất thường, không phải phát hiện tín hiệu lạ.

**Vì sao autoencoder chứ không phải bộ phân loại.** Muốn huấn luyện bộ phân loại "bình thường so với
bất thường" thì cần dữ liệu bất thường có gán nhãn, và dữ liệu đó hầu như không thu được trong nhà
thật: không ai muốn người thân bị ngã để có mẫu. Autoencoder đi đường vòng: chỉ học cách tái tạo
chuỗi bình thường, rồi coi chuỗi nào tái tạo kém là bất thường. Điểm bất lợi là mô hình không phân
biệt được *loại* bất thường, nên phần giải thích phải do bộ luật đảm nhiệm.

**Vì sao chọn GRU thay vì LSTM.** GRU có hai cổng thay vì ba, ít tham số hơn trên cùng kích thước
ẩn. Với bộ dữ liệu nhỏ như ở đây, ít tham số hơn giúp giảm nguy cơ học thuộc và huấn luyện nhanh
hơn, trong khi khả năng ghi nhớ phụ thuộc dài hạn không phải yếu tố quyết định với chuỗi chỉ 8 bước.
Kiến trúc GRU theo công trình của Cho và cộng sự [9].

**Ngưỡng phải chọn trên tập validation, không phải tập test.** Đây là điểm từng bị làm sai trong
phiên bản đầu và đã được sửa. Bản cũ lấy phân vị 0,99 của sai số tái tạo trên chính các ngày được
dùng để đánh giá, nên ngưỡng được chọn vừa khít với tập test và chỉ số báo cáo cao hơn thực tế. Quy
trình hiện tại chia ba phần không giao nhau: các ngày dùng để huấn luyện, các ngày dùng để chọn
ngưỡng, và các ngày dùng để đánh giá. Ngưỡng được ghi lại vào `anomaly_threshold.json` kèm danh sách
ngày test, để script đánh giá biết chính xác phải chạy trên những ngày nào.

**Kết hợp với bộ luật.** Autoencoder chỉ bắt được bất thường về *hình dạng* chuỗi. Nhiều bất thường
trong thực tế lại mang tính ngữ nghĩa và rất đơn giản để diễn đạt bằng luật: ở một phòng lâu hơn
ngưỡng cho phép, chuyển phòng không có trong sơ đồ nhà, hoặc đi lại nhiều vào ban đêm. Bộ luật
`RuleEngine` xử lý những trường hợp đó và đóng góp phần lớn số cảnh báo trong thực nghiệm; vai trò
của autoencoder là nhóm bất thường về quỹ đạo mà luật không diễn đạt được. Việc tách bạch hai nguồn
này được giữ nguyên trong phần đánh giá ở mục 8.3, thay vì gộp lại thành một con số duy nhất.

### 3.4. Phát hiện ngã (Mobile Sensor)

Sử dụng gia tốc kế 3 trục trên điện thoại (100Hz):
- **Magnitude:** `sqrt(ax² + ay² + az²)`
- **State machine:** NO_DATA → MOVING ↔ STILL → IMPACT_RECORDED
- **Ngưỡng impact:** Magnitude > 18g (configurable) trong 20ms → theo dõi 20s → nếu STILL > 5s → FALL_DETECTED
- **Orientation:** Portrait/Landscape/Flat từ vector trọng lực

**Cơ sở vật lý.** Khi điện thoại nằm yên, vector gia tốc đo được chủ yếu là trọng lực nên độ lớn
xấp xỉ 1 g. Trong lúc rơi tự do, độ lớn giảm mạnh về gần 0 g. Va chạm với nền tạo ra một xung rất
lớn trong khoảng vài chục mili giây. Sau va chạm, nếu người bị ngã thì thường nằm yên một lúc. Ba
pha nối tiếp nhau đó — rơi, va chạm, nằm yên — là dấu hiệu phân biệt cú ngã với việc đặt điện thoại
xuống bàn.

**Vì sao dùng máy trạng thái thay vì bộ phân loại.** Một bộ phân loại trên từng mẫu gia tốc sẽ bắt
cả những xung mạnh vô hại, ví dụ khi đặt điện thoại xuống. Máy trạng thái buộc phải có *chuỗi* sự
kiện: một xung vượt ngưỡng đưa hệ thống sang trạng thái theo dõi, và chỉ khi sau đó tín hiệu vẫn
yên trong một khoảng mới kết luận là ngã. Cách này dễ giải thích và dễ chỉnh ngưỡng theo từng thiết
bị hơn, đổi lại phải chọn ngưỡng bằng tay.

Hướng cầm máy được suy ra từ chính vector trọng lực: khi người dùng nhìn màn hình thì trục nào chiếm
ưu thế trong vector đó là trục dọc của máy. Hướng cầm không dùng để phát hiện ngã, mà để gắn nhãn cho
mẫu thu thập, vì biểu diễn RSSI thay đổi theo hướng cầm điện thoại.

**Giới hạn cần nói rõ.** Phần này chỉ hoạt động khi người được giám sát mang theo điện thoại và ứng
dụng đang mở; trình duyệt trên điện thoại tự giảm tần suất đọc cảm biến khi ứng dụng chạy nền. Đây
là lý do phần này được thiết kế như một tuỳ chọn cộng thêm chứ không phải nguồn dữ liệu chính, và
mục 8.4 ghi nhận là **chưa kiểm thử** với người ngã thật.

### 3.5. Topology-aware Filtering

Sử dụng đồ thị chuyển phòng (topology) để lọc dự đoán:
- Ma trận chuyển trạng thái T[i][j] = 1 nếu phòng i kề phòng j
- Viterbi-like filter: `P_t = normalize(T^T * P_{t-1} * likelihood_t)`
- Loại bỏ chuyển phòng không hợp lý (nhảy từ Phòng ngủ → Phòng bếp không qua Phòng khách)

Đây là một phép cập nhật Bayes rút gọn. Phân bố ở bước trước đóng vai trò tiên nghiệm, ma trận kề
đóng vai trò xác suất chuyển, và đầu ra của mô hình phân loại đóng vai trò hàm hợp lý. Kết quả được
chuẩn hoá lại thành phân bố xác suất để dùng cho bước kế tiếp.

Ma trận kề được khai báo thủ công trong `config.yaml` theo bố cục thật của căn nhà (`room_topology`),
vì không có cách nào suy ra từ dữ liệu rằng phòng ngủ và nhà bếp không kề nhau. Cách khai báo này
cũng là điểm dễ mở rộng: thêm phòng mới thì sửa một dòng cấu hình.

Tham số `topology.self_weight` quyết định mức ưu tiên cho khả năng ở lại phòng cũ so với chuyển đi,
được đặt 0,75. Đặt cao hơn 0,5 vì trong nhà, phần lớn các bước thời gian là người vẫn ở nguyên một
chỗ; nếu để thấp, bộ lọc sẽ đổi phòng theo từng dao động nhỏ của RSSI. Giá trị này được chọn trên
tập validation cùng lúc với các tham số khác.

Ý tưởng dùng một meta-model và tách hai pha học và theo dõi được tham khảo từ FIND3 [4], còn cách
chia sẻ encoder giữa hai đầu ra được tham khảo từ ARIL [3]. Khóa luận không dùng lại mã nguồn của
các dự án đó; phần đọc mã chỉ để đối chiếu cách tổ chức trước khi tự viết.

---

## 4. THIẾT KẾ HỆ THỐNG

### 4.1. Sơ đồ Use Case

| Actor | Use Cases |
|-------|-----------|
| **Người cao tuổi** | Được giám sát (passive), mang điện thoại (tùy chọn) |
| **Người chăm sóc/Người thân** | Xem dashboard, nhận cảnh báo, cấu hình ngưỡng |
| **Quản trị viên (Admin)** | Quản lý user, home, device, xem log bảo mật |
| **Hệ thống bên ngoài** | Nhận webhook cảnh báo (Telegram, ntfy, IFTTT) |

### 4.2. Sơ đồ Sequence - Giám sát Realtime

```
Android App          Flask Server              Inference Engine          Database
   │                    │                          │                        │
   ├─ POST /api/scan ──►│                          │                        │
   │                    ├─ preprocess(wifi) ──────►│                        │
   │                    │◄─ fingerprint vector ────┤                        │
   │                    ├─ room_net.predict() ────►│                        │
   │                    │◄─ room_probs ────────────┤                        │
   │                    ├─ gru_ae.predict() ──────►│                        │
   │                    │◄─ anomaly_score ─────────┤                        │
   │                    ├─ topology_filter() ──────►│                        │
   │                    │◄─ final_room ────────────┤                        │
   │                    ├─ persist_result() ──────►│                        │
   │                    │                          ├─ INSERT prediction ───►│
   │                    │                          │                        │
   │◄─ JSON response ───┤                          │                        │
   │   {room, conf,     │                          │                        │
   │    anomaly, ...}   │                          │                        │
```

### 4.3. Sơ đồ Class - Core Modules

```
SmartHomeDatabase
├── +create_user(email, pwd_hash, name)
├── +create_home(owner_id, name)
├── +create_room(home_id, name)
├── +create_device(home_id, name) → (device, token)
├── +authenticate_device(token_hash)
├── +record_wifi_scan(...) → {duplicate, ready}
├── +save_prediction(home_id, result)
├── +save_alert(home_id, alert)
├── +list_alerts(home_id, limit)
├── +prediction_history(home_id, limit)
├── +calibration_progress(home_id, ...)
└── +export_scans(home_id)

SmartHomeInferenceEngine
├── +process_scan(wifi_dict, timestamp) → {room, confidence, anomaly, ...}
├── +train_room_model(home_id) → model_path
├── +train_anomaly_model(home_id) → model_path
└── +calibration_progress(home_id)

MobileSensorMonitor
├── +update(device_id, accel, timestamp) → {state, impact, orientation}
├── +status(device_id) → {state, last_impact, ...}
└── +alerts → List[Alert]
```

### 4.4. Sơ đồ State - Mobile Sensor

```
                    ┌─────────────┐
                    │   NO_DATA   │
                    └──────┬──────┘
                           │ first accel
                           ▼
              ┌─────────────────────────┐
              │        MOVING           │◄──────────────────┐
              │ (magnitude > 0.8g)      │                   │
              └───────────┬─────────────┘                   │
                          │ magnitude < 0.25g              │ magnitude > 0.8g
                          ▼                                  │
              ┌─────────────────────────┐                   │
              │        STILL            │                   │
              │ (magnitude < 0.25g)     │                   │
              └───────────┬─────────────┘                   │
                          │ magnitude > 18g (impact)       │
                          ▼                                  │
              ┌─────────────────────────┐                   │
              │   IMPACT_RECORDED       │                   │
              │ (follow-up 20s)         │                   │
              └───────────┬─────────────┘                   │
                          │ still > 5s after impact        │
                          ▼                                  │
              ┌─────────────────────────┐                   │
              │      FALL_DETECTED      │                   │
              │ (alert + webhook)       │                   │
              └───────────┬─────────────┘                   │
                          │ reset timeout                    │
                          ▼                                  │
                        (back to STILL/MOVING)
```

### 4.5. Sơ đồ Deployment

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Host (Linux)                      │
│  ┌──────────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  an-tam-home:2310 │  │   Nginx      │  │  Certbot     │  │
│  │  (Gunicorn+Flask) │  │  (Reverse    │  │  (Let's      │  │
│  │  Port 5000        │  │   Proxy)     │  │   Encrypt)   │  │
│  │                   │  │  Port 80/443 │  │              │  │
│  └────────┬──────────┘  └──────┬───────┘  └──────┬───────┘  │
│           │                    │                   │          │
│           └────────────────────┼───────────────────┘          │
│                                ▼                              │
│                    ┌────────────────────────┐                 │
│                    │   Docker Volumes       │                 │
│                    │  ./data:/app/data      │                 │
│                    │  ./models:/app/models  │                 │
│                    └────────────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
┌─────────────────────┐      ┌─────────────────────┐
│   Cloudflare        │      │   Android App       │
│   (DNS + Proxy +    │      │   (LAN: NSD HTTP)   │
│    WAF + SSL)       │      │   (WAN: HTTPS +     │
└─────────────────────┘      │    Cert Pinning)    │
                             └─────────────────────┘
```

---

## 5. TRIỂN KHAI PHẦN CỨNG

### 5.1. Yêu cầu tối thiểu

| Thiết bị | Cấu hình khuyến nghị |
|----------|---------------------|
| **Server** | Raspberry Pi 4 (4GB/8GB) hoặc Mini PC x86 (Intel NUC, 4GB RAM, 32GB SSD) |
| **WiFi Router** | Dual-band 2.4/5GHz, hỗ trợ 802.11n/ac, ít nhất 3 AP trong nhà |
| **Android Phone** | Android 10+, gia tốc kế, WiFi, pin > 3000mAh (nếu bật cảm biến ngã) |
| **Mạng** | LAN ổn định, có thể mở port 5000 hoặc dùng Cloudflare Tunnel |

### 5.2. Bố trí Access Point

Để độ chính xác định vị tốt, cần ít nhất 3 AP nghe được ở mỗi phòng:

```
         [AP1 - Living Room]          [AP2 - Bedroom]
                ●                            ●
               / \                          / \
              /   \                        /   \
             /     \                      /     \
            ▼       ▼                    ▼       ▼
        ┌─────┐   ┌─────┐            ┌─────┐   ┌─────┐
        │ Kit │   │Bed  │            │Bath │   │Kit  │
        │chen │   │room │            │room │   │chen2│
        └─────┘   └─────┘            └─────┘   └─────┘
               \     /                      \     /
                \   /                        \   /
                 \ /                          \ /
                  ●                            ●
          [AP3 - Hallway]             [AP4 - Kitchen]
```

**Lưu ý:** AP cùng kênh (channel) gây nhiễu. Nên cấu hình kênh 1, 6, 11 cho 2.4GHz; kênh 36, 40, 44, 48 cho 5GHz.

### 5.3. Android Phone Placement (nếu bật cảm biến ngã)

- **Vị trí:** Túi áo trước, hoặc đaieo ngực, hoặc túi quần (cố định)
- **Tránh:** Túi sau quần (ngồi đè), túi áo khoác dễ rơi
- **Sạc:** Sạc đêm, dùng power bank nếu theo dõi 24/7
- **Cài đặt:** Tắt tối ưu pin cho app, cho phép chạy nền, cấp quyền Location + Nearby WiFi

---

## 6. PHÁT TRIỂN PHẦN MỀM

### 6.1. Backend - Flask Server

#### 6.1.1. Cấu trúc thư mục

```
server/
├── app.py                    # Entry point, app factory
├── app_state.py              # Shared state (DB, engines, runtime)
├── app_security.py           # Auth, rate limit, CSP, AttemptLimiter
├── app_services.py           # Business logic helpers
├── security_middleware.py    # Rate limit, request guard, headers
├── routes/
│   ├── __init__.py
│   ├── auth_views.py         # /api/auth/*
│   ├── home_views.py         # /api/homes/*
│   ├── room_views.py         # /api/rooms/*
│   ├── track_views.py        # /api/scan, /api/collect, /api/sensor
│   └── training_views.py     # /api/training/*
├── templates/
│   └── dashboard.html        # PWA dashboard
├── static/
│   ├── app.js               # Dashboard logic
│   ├── style.css            # Desktop styles
│   ├── mobile.css           # Mobile responsive
│   ├── manifest.webmanifest  # PWA manifest
│   └── service-worker.js    # Offline caching
├── Dockerfile
├── docker-compose.yml
└── requirements*.txt
```

#### 6.1.2. Rate Limiting (app_security.py)

```python
class AttemptLimiter:
    """Chặn dò mật khẩu / dò mã chia sẻ bằng cách thử lặp.
    
    Mỗi khóa (email khi đăng nhập, user khi tham gia nhà) chỉ được thất bại
    tối đa `max_attempts` lần trong `window_seconds`; thành công thì xóa đếm.
    Bộ đếm nằm trong RAM — khởi động lại server là xóa — đủ cho máy chủ
    gia đình mà không cần thêm thư viện.
    """
    
    def __init__(self, max_attempts: int, window_seconds: float):
        self.max_attempts = int(max_attempts)
        self.window_seconds = float(window_seconds)
        self._attempts: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def record_failure(self, key: str) -> bool:
        """Ghi nhận thất bại. Trả về True nếu đã vượt ngưỡng (bị khóa)."""
        with self._lock:
            now = time.time()
            window_start = now - self.window_seconds
            # Dọn cửa sổ trượt
            self._attempts[key] = [t for t in self._attempts[key] if t > window_start]
            self._attempts[key].append(now)
            return len(self._attempts[key]) >= self.max_attempts

    def record_success(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)

    def is_blocked(self, key: str) -> bool:
        with self._lock:
            now = time.time()
            window_start = now - self.window_seconds
            attempts = [t for t in self._attempts.get(key, []) if t > window_start]
            return len(attempts) >= self.max_attempts
```

#### 6.1.3. Security Headers (app_security.py)

```python
def apply_security_headers(response: Response) -> Response:
    """Áp dụng các header bảo mật chuẩn cho mọi response."""
    # CSP chặt chẽ - không unsafe-eval
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; font-src 'self'; "
        "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
    )
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response
```

#### 6.1.4. Security Middleware (security_middleware.py)

```python
class RateLimiter:
    """Giới hạn tần suất sliding window theo (nhóm endpoint, client)."""
    
    BLOCK_SECONDS = 60
    MAX_TRACKED_CLIENTS = 4096
    
    def _trust_proxy(self) -> bool:
        return os.getenv("SMART_HOME_TRUST_PROXY", "0") == "1"

    def _client_id(self) -> str:
        if self._trust_proxy():
            forwarded = request.headers.get("X-Forwarded-For", "")
            ip = forwarded.split(",")[0].strip() if forwarded else request.remote_addr
        else:
            ip = request.remote_addr or "?"
        ua = request.headers.get("User-Agent", "").encode("utf-8", "ignore")
        return f"{ip}:{hashlib.sha256(ua).hexdigest()[:8]}"
```

#### 6.1.5. Webhook Alert (app_services.py)

```python
def _webhook_url() -> str:
    value = app_state.cfg.get("alerts", {}).get("webhook_url", "")
    url = str(value or "").strip()
    if len(url) > 500 or not url.lower().startswith(("http://", "https://")):
        return ""
    return url

def notify_alert(home_id: int, home_name: str, alert: dict) -> None:
    """Đẩy cảnh báo CRITICAL ra webhook nếu người vận hành đã cấu hình."""
    if str(alert.get("status", "")).upper() != "CRITICAL" or not _webhook_url():
        return
    threading.Thread(
        target=_post_webhook,
        args=(home_id, home_name or f"Nhà #{home_id}", dict(alert)),
        daemon=True,
    ).start()

def _post_webhook(home_id: int, home_name: str, alert: dict) -> None:
    url = _webhook_url()
    if not url:
        return
    payload = {
        "event": "alert",
        "home_id": home_id,
        "home": home_name,
        "status": alert.get("status"),
        "room": alert.get("room"),
        "reasons": alert.get("reasons", []),
        "timestamp": alert.get("timestamp"),
    }
    try:
        requests.post(url, json=payload, timeout=5, allow_redirects=False)
    except requests.RequestException as exc:
        logging.getLogger(__name__).warning("Không gửi được webhook cảnh báo: %s", exc)
```

### 6.2. Android Collector

#### 6.2.1. Certificate Pinning (MainActivity.kt)

```kotlin
object CertificatePinner {
    private const val TAG = "CertificatePinner"
    
    private fun loadPins(context: Context?): List<String> {
        if (context == null) return emptyList()
        return try {
            context.resources.openRawResource(R.raw.cert_pins).bufferedReader().readLines()
                .map { it.trim() }
                .filter { it.isNotEmpty() && !it.startsWith("#") }
        } catch (_: Exception) {
            emptyList()
        }
    }
    
    private fun pinOf(cert: X509Certificate): String {
        val digest = MessageDigest.getInstance("SHA-256").digest(cert.publicKey.encoded)
        return "sha256/" + android.util.Base64.encodeToString(digest, android.util.Base64.NO_WRAP)
    }
    
    fun isPinned(hostname: String, session: SSLSession, context: Context?): Boolean {
        val pins = loadPins(context)
        if (pins.isEmpty()) return true  // chưa cấu hình pin -> chỉ dùng trust store hệ thống
        val peer = session.peerCertificates
        if (peer.isNullOrEmpty()) return false
        return peer.any { it is X509Certificate && pinOf(it) in pins }
    }
    
    fun pinnedSslContext(context: Context?): SSLContext {
        val trustManager = object : X509TrustManager {
            override fun checkClientTrusted(chain: Array<X509Certificate>?, authType: String?) {}
            
            override fun checkServerTrusted(chain: Array<X509Certificate>?, authType: String?) {
                if (chain.isNullOrEmpty()) {
                    throw CertificateException("Chuỗi chứng chỉ rỗng")
                }
                chain.forEach { it.checkValidity() }
                val pins = loadPins(context)
                if (pins.isNotEmpty() && chain.none { pinOf(it) in pins }) {
                    throw CertificateException("Certificate pinning thất bại cho server")
                }
            }
            
            override fun getAcceptedIssuers(): Array<X509Certificate> = arrayOf()
        }
        return SSLContext.getInstance("TLS").apply { init(null, arrayOf(trustManager), null) }
    }
}
```

#### 6.2.2. Network Security Config (res/xml/network_security_config.xml)

```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <base-config cleartextTrafficPermitted="true">
        <!-- CHO PHÉP HTTP CHỈ CHO LAN NSD AUTO-DISCOVERY.
             Máy chủ gia đình không có chứng chỉ công khai cho IP LAN.
             Dữ liệu gửi là RSSI với BSSID đã băm SHA-256 (không PII).
             KHI DÙNG TUNNEL/HTTPS: domain config dưới sẽ enforce pinning. -->
        <trust-anchors>
            <certificates src="system" />
        </trust-anchors>
    </base-config>

    <domain-config cleartextTrafficPermitted="false">
        <domain includeSubdomains="true">your-server-domain.example</domain>
        <pin-set expiration="2027-11-01">
            <pin algorithm="SHA-256">REPLACE_WITH_PRIMARY_PIN</pin>
            <pin algorithm="SHA-256">REPLACE_WITH_BACKUP_PIN</pin>
        </pin-set>
        <trust-anchors>
            <certificates src="system" />
        </trust-anchors>
    </domain-config>

    <debug-overrides>
        <trust-anchors>
            <certificates src="system" />
            <certificates src="user" />
        </trust-anchors>
    </debug-overrides>
</network-security-config>
```

#### 6.2.3. Hash BSSID Chuẩn Hóa (MainActivity.kt)

```kotlin
private fun hashBssid(bssid: String): String {
    // Viết thường trước khi băm: netsh trên PC trả BSSID hoa còn
    // Android trả thường — cùng thiết bị phải cho CÙNG tên AP
    // Vector kiểm chứng: aa:bb:cc:dd:ee:ff -> AP_c1582e87c802
    val digest = MessageDigest.getInstance("SHA-256")
        .digest(bssid.trim().lowercase().toByteArray())
    return "AP_" + digest.take(6).joinToString("") { "%02x".format(it) }
}
```

#### 6.2.4. NSD Auto-Discovery

```kotlin
private fun startDiscovery() {
    val nsdManager = getSystemService(Context.NSD_SERVICE) as NsdManager
    val serviceType = "_antam._tcp."
    
    val discoveryListener = object : NsdManager.DiscoveryListener {
        override fun onDiscoveryStarted(serviceType: String) {
            runOnUiThread { discoveryStatus.text = "Đang tìm server..." }
        }
        
        override fun onServiceFound(serviceInfo: NsdServiceInfo) {
            nsdManager.resolveService(serviceInfo, resolveListener)
        }
        
        override fun onServiceLost(serviceInfo: NsdServiceInfo) {
            // Server mất tín hiệu
        }
        
        override fun onDiscoveryStopped(serviceType: String) {}
        override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {}
        override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {}
    }
    
    val resolveListener = object : NsdManager.ResolveListener {
        override fun onResolveFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {}
        
        override fun onServiceResolved(serviceInfo: NsdServiceInfo) {
            val host = serviceInfo.host?.hostAddress ?: return
            val port = serviceInfo.port
            runOnUiThread {
                backendUrl.setText("http://$host:$port")
                discoveryStatus.text = "Đã tìm thấy server: $host:$port"
                Log.d("NSD", "Tự động tìm thấy server tại $host:$port")
            }
        }
    }
    
    nsdManager.discoverServices("_antam._tcp.", NsdManager.PROTOCOL_DNS_SD, discoveryListener)
}
```

### 6.3. Database Schema (SQLite)

```sql
-- Users
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    created_at REAL NOT NULL
);

-- Homes
CREATE TABLE homes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at REAL NOT NULL
);

-- Rooms
CREATE TABLE rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_id INTEGER NOT NULL REFERENCES homes(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    max_dwell_minutes REAL NOT NULL DEFAULT 60,
    created_at REAL NOT NULL,
    _name_key TEXT NOT NULL DEFAULT ''  -- normalized key for lookup
);

-- Collector Devices
CREATE TABLE collector_devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_id INTEGER NOT NULL REFERENCES homes(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    platform TEXT NOT NULL DEFAULT 'android',
    token_hash TEXT NOT NULL UNIQUE,      -- SHA-256(token)
    token_hint TEXT NOT NULL,             -- 6 chars đầu token
    last_seen_at REAL,
    last_scan_at REAL,
    last_ap_count INTEGER,
    last_battery_pct REAL,
    last_throttled INTEGER,
    created_at REAL NOT NULL
);

-- Collection Sessions (Offline training)
CREATE TABLE collection_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_id INTEGER NOT NULL REFERENCES homes(id) ON DELETE CASCADE,
    room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    collector_device_id INTEGER REFERENCES collector_devices(id) ON DELETE SET NULL,
    session_code TEXT NOT NULL,
    target_samples INTEGER NOT NULL,
    started_at REAL NOT NULL,
    completed_at REAL,
    status TEXT NOT NULL DEFAULT 'IN_PROGRESS',
    UNIQUE(home_id, room_id, session_code)
);

-- WiFi Scans (fingerprint data)
CREATE TABLE wifi_scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_session_id INTEGER NOT NULL REFERENCES collection_sessions(id) ON DELETE CASCADE,
    home_id INTEGER NOT NULL REFERENCES homes(id) ON DELETE CASCADE,
    room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    device_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    orientation TEXT NOT NULL DEFAULT 'UNKNOWN',
    ap_count INTEGER NOT NULL,
    wifi_json TEXT NOT NULL,           -- {"AP_xxx": rssi, ...}
    scan_ts REAL,                       -- epoch seconds từ Android ScanResult.timestamp
    wifi_hash TEXT                      -- SHA-256 hash của wifi_json (dedup)
);

-- Predictions (Realtime inference)
CREATE TABLE predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_id INTEGER NOT NULL REFERENCES homes(id) ON DELETE CASCADE,
    timestamp REAL NOT NULL,
    room_name TEXT,
    confidence REAL,
    status TEXT NOT NULL,              -- NORMAL, WARNING, CRITICAL
    activity TEXT,
    anomaly_score REAL,
    reasons_json TEXT NOT NULL DEFAULT '[]'
);

-- Sensor Samples (Mobile sensor)
CREATE TABLE sensor_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_id INTEGER NOT NULL REFERENCES homes(id) ON DELETE CASCADE,
    device_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    z REAL NOT NULL,
    magnitude REAL NOT NULL,
    state TEXT NOT NULL,
    possible_impact INTEGER NOT NULL DEFAULT 0
);

-- Alerts
CREATE TABLE alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_id INTEGER NOT NULL REFERENCES homes(id) ON DELETE CASCADE,
    timestamp REAL NOT NULL,
    room_name TEXT,
    status TEXT NOT NULL,              -- WARNING, CRITICAL
    source TEXT NOT NULL,              -- 'wifi', 'sensor', 'device_offline'
    reasons_json TEXT NOT NULL,
    device_id TEXT,                    -- collector_device.id (text)
    resolved_at REAL
);

-- Home Shares (Mã 6 số)
CREATE TABLE home_shares (
    code TEXT PRIMARY KEY,             -- 6 digits
    home_id INTEGER NOT NULL REFERENCES homes(id) ON DELETE CASCADE,
    created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    revoked_at REAL
);

-- Home Members
CREATE TABLE home_members (
    home_id INTEGER NOT NULL REFERENCES homes(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at REAL NOT NULL,
    PRIMARY KEY (home_id, user_id)
);

-- Indexes
CREATE INDEX idx_wifi_scans_home_room ON wifi_scans(home_id, room_id, timestamp);
CREATE INDEX idx_wifi_scans_session_ts ON wifi_scans(collection_session_id, scan_ts);
CREATE INDEX idx_predictions_home_time ON predictions(home_id, timestamp DESC);
CREATE INDEX idx_alerts_home_time ON alerts(home_id, timestamp DESC);
CREATE INDEX idx_sensor_home_time ON sensor_samples(home_id, timestamp DESC);
```

### 6.4. Frontend - Web Dashboard (PWA)

#### 6.4.1. Real-time Updates (SSE)

```javascript
// app.js - SSE connection với reconnect exponential backoff
class SSEClient {
    constructor(url, onMessage, onError) {
        this.url = url;
        this.onMessage = onMessage;
        this.onError = onError;
        this.retryDelay = 1000;
        this.maxRetryDelay = 30000;
        this.connect();
    }
    
    connect() {
        this.eventSource = new EventSource(this.url);
        this.eventSource.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data);
                this.onMessage(data);
                this.retryDelay = 1000; // reset on success
            } catch (e) { console.warn('SSE parse error', e); }
        };
        this.eventSource.onerror = () => {
            this.eventSource.close();
            setTimeout(() => this.connect(), this.retryDelay);
            this.retryDelay = Math.min(this.retryDelay * 2, this.maxRetryDelay);
        };
    }
}
```

#### 6.4.2. Circular Probability Gauge (SVG)

```javascript
function renderGauge(containerId, probability, roomName) {
    const container = document.getElementById(containerId);
    const radius = 50;
    const strokeWidth = 8;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference * (1 - probability);
    
    container.innerHTML = `
        <svg width="120" height="120" viewBox="0 0 120 120">
            <circle cx="60" cy="60" r="${radius}" 
                    stroke="#e0e0e0" stroke-width="${strokeWidth}" fill="none"/>
            <circle cx="60" cy="60" r="${radius}" 
                    stroke="${getColor(probability)}" stroke-width="${strokeWidth}" 
                    fill="none" stroke-dasharray="${circumference}" 
                    stroke-dashoffset="${offset}" 
                    style="transform: rotate(-90deg); transform-origin: 60px 60px;
                           transition: stroke-dashoffset 0.5s ease;"/>
            <text x="60" y="65" text-anchor="middle" font-size="24" fill="#333">
                ${Math.round(probability * 100)}%
            </text>
            <text x="60" y="95" text-anchor="middle" font-size="12" fill="#666">
                ${roomName}
            </text>
        </svg>
    `;
}
```

#### 6.4.3. Responsive CSS (mobile.css)

```css
/* Mobile-first breakpoints */
@media (max-width: 480px) {
    .dashboard-grid { grid-template-columns: 1fr; }
    .gauge-container { width: 100px; height: 100px; }
    .btn { padding: 12px 16px; font-size: 16px; }
    .card { padding: 12px; }
}

@media (min-width: 481px) and (max-width: 768px) {
    .dashboard-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (min-width: 769px) {
    .dashboard-grid { grid-template-columns: repeat(4, 1fr); }
}

/* Touch-friendly */
.btn { min-height: 44px; min-width: 44px; }
input, select { font-size: 16px; /* prevent zoom on iOS */ }
```

#### 6.4.4. PWA Manifest & Service Worker

```json
// manifest.webmanifest
{
  "name": "An Tâm Home",
  "short_name": "An Tâm",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#f8f9fa",
  "theme_color": "#2563eb",
  "icons": [
    {"src": "/static/app-icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any maskable"}
  ]
}
```

```javascript
// service-worker.js - Cache-first strategy
const CACHE_NAME = 'antam-v1';
const ASSETS = ['/', '/static/app.js', '/static/style.css', '/static/mobile.css', '/static/app-icon.svg'];

self.addEventListener('install', (e) => {
    e.waitUntil(caches.open(CACHE_NAME).then(c => c.addAll(ASSETS)));
});

self.addEventListener('fetch', (e) => {
    e.respondWith(
        caches.match(e.request).then(r => r || fetch(e.request))
    );
});
```

---

## 7. BẢO MẬT HỆ THỐNG

### 7.1. Mô hình đe dọa (Threat Model)

| Asset | Threat | Mitigation |
|-------|--------|------------|
| **Dữ liệu fingerprint** | Eavesdropping LAN | HTTPS + Certificate Pinning (WAN), NSD HTTP chỉ LAN |
| **Session cookie** | Session hijacking | HttpOnly, Secure, SameSite=Lax, rotate secret |
| **Device token** | Token theft | SHA-256 hash lưu DB, hint 6 chars, revokeable |
| **Password** | Brute force, rainbow table | scrypt (N=32768, r=8, p=1), rate limit 5/5min |
| **API endpoints** | Injection, abuse | Parameterized queries, rate limit per endpoint |
| **Webhook** | SSRF, redirect | allow_redirects=False, timeout 5s, URL validation |
| **Model files** | Pickle RCE | `torch.load(weights_only=True)` |

### 7.2. Authentication & Authorization

```python
# app_security.py - Decorators
def login_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if not flask_session.get("user_id"):
            return jsonify({"error": "AUTH_REQUIRED"}), 401
        return function(*args, **kwargs)
    return wrapper

def require_mutation_context() -> tuple[dict | None, dict | None, Response | None]:
    """Context ghi dữ liệu: device token hoặc tài khoản chủ nhà.
    
    Bearer device token được coi như chủ nhà; đăng nhập session thì
    tài khoản thành viên (qua mã chia sẻ) không được ghi.
    """
    home, device = request_home_context()
    if not home:
        return None, None, (jsonify({"error": "Đăng nhập hoặc cung cấp Bearer device token"}), 401)
    if device is None:
        user_id = flask_session.get("user_id")
        if not user_id or not app_state.db.is_home_owner(home["id"], int(user_id)):
            return None, None, (jsonify({"error": "HOME_OWNER_REQUIRED", "detail": "Tài khoản chia sẻ chỉ có quyền xem"}), 403)
    return home, device, None
```

### 7.3. Rate Limiting Chi Tiết

| Endpoint Group | Limit | Window | Implementation |
|----------------|-------|--------|----------------|
| `/api/auth/*` | 10 req | 60s | AttemptLimiter (5 fails/5min) + RateLimiter |
| `/api/collect` | 240 req | 60s | RateLimiter (IP+UA) |
| `/api/scan` | 240 req | 60s | RateLimiter |
| `/api/sensor` | 240 req | 60s | RateLimiter |
| `/api/*` (other) | 300 req | 60s | RateLimiter |
| `/api/health` | Unlimited | - | Bỏ qua |

### 7.4. Certificate Pinning Details

**Tạo pin từ chứng chỉ:**
```bash
openssl x509 -in cert.pem -pubkey -noout | \
openssl pkey -pubin -outform DER | \
openssl dgst -sha256 -binary | base64
# Output: AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=
```

**Cập nhật Android:**
1. Thay pin trong `res/raw/cert_pins.txt` (mỗi dòng 1 pin)
2. Cập nhật `network_security_config.xml` pin-set
3. Build release APK: `./gradlew assembleRelease`

### 7.5. Docker Security

```dockerfile
# Multi-stage build - Production stage
FROM python:3.11-slim AS prod

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

COPY requirements-docker.txt ./
RUN pip install --upgrade pip && pip install -r requirements-docker.txt

COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser server/ ./server/
COPY --chown=appuser:appuser config.yaml ./
COPY --chown=appuser:appuser .env.example ./

RUN mkdir -p /app/data /app/models && chown -R appuser:appuser /app/data /app/models

USER appuser
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health')" || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:5000", \
     "--worker-class", "gthread", "--workers", "2", "--threads", "8", \
     "--timeout", "300", "server.wsgi:application"]
```

Worker `gthread` được chọn thay vì `sync` vì dashboard dùng Server-Sent Events ở `/api/stream`:
worker đồng bộ giữ trọn một tiến trình cho mỗi kết nối SSE và chặn các request khác. Người dùng
`appuser` cũng được tạo thư mục home riêng, vì gunicorn 26 mở một control socket trong `$HOME` và
`useradd -r` không tạo thư mục này.

### 7.6. Hạn mức tần suất khi chạy nhiều tiến trình

Hạn mức ở mục 7.3 mặc định nằm trong RAM của từng tiến trình. Cách đó đủ cho một tiến trình duy
nhất, nhưng khi chạy nhiều worker hoặc nhiều container thì mỗi tiến trình giữ một bộ đếm riêng, và
giới hạn thực tế nhân lên theo số tiến trình. Với hai worker, ngưỡng 30 request mỗi phút cho nhóm
`auth` trở thành 60.

Đặt biến `REDIS_HOST` thì bộ đếm chuyển sang Redis dùng chung. Toàn bộ thao tác *cắt cửa sổ, đếm,
kiểm tra trạng thái chặn và ghi nhận request* được gộp vào một script Lua, nên Redis thực thi trọn
vẹn trong một lượt. Nếu tách thành hai lượt đọc rồi ghi, hai request đến cùng lúc đều thấy cửa sổ
còn chỗ và cùng ghi; đo trên máy phát triển với 60 request đồng thời và ngưỡng 10, bản hai lượt cho
qua 29 request, bản dùng Lua cho qua đúng 10.

Khoá định danh client chỉ dùng địa chỉ IP, không trộn thêm `User-Agent`. `User-Agent` do phía gọi
tự khai, nên nếu đưa vào khoá thì chỉ cần đổi giá trị đó mỗi request là có một bộ đếm mới và vượt
được hạn mức. Trường `X-Forwarded-For` cũng chỉ được tin khi biến `SMART_HOME_TRUST_PROXY` được bật,
tức là khi máy chủ thật sự nằm sau một reverse proxy tin cậy.

Khi Redis không nối được, ứng dụng ghi cảnh báo rồi lùi về chế độ RAM cho tiến trình đó. Việc ghi
cảnh báo là bắt buộc: nếu im lặng, người vận hành sẽ tưởng hạn mức vẫn đang được chia sẻ trong khi
thực tế mỗi tiến trình đếm riêng.

Còn lại chưa chuyển sang Redis: trạng thái cảm biến chuyển động, lịch sử suy luận tạm thời và tiến
độ huấn luyện vẫn nằm trong RAM từng tiến trình. Muốn chạy nhiều instance thật thì các phần này
cũng phải chuyển đi, hoặc phải ghim mỗi căn nhà vào một instance cố định.

---

## 8. KIỂM THỬ VÀ ĐÁNH GIÁ

### 8.1. Môi trường thử nghiệm

| Mục | Cấu hình |
|------------|----------|
| Máy chạy huấn luyện và đo số liệu | Máy phát triển Windows, CPU thường, PyTorch CPU (torch 2.15.0+cpu) |
| Dữ liệu | Mô phỏng v2 (generate_synthetic_data.py): 8 session, 5 phòng; split theo session 6/1/1 |
| Seed | 42 (mọi script; tái lập được theo results/g3_multitask/README.md) |
| Baseline | SimpleCNN, RandomForest, MLP, kNN (scikit-learn) |

Chưa thực hiện: đo trên thiết bị edge (Raspberry Pi/ESP32) và trên mạng LAN
thật với AP vật lý — xem mục 10.2.

### 8.2. Kết quả định vị phòng (test S08, seed 42)

RoomNetLite (results/g3_multitask/models/room_test_metrics.json):

| Chỉ số | Giá trị |
|--------|---------|
| Test Accuracy | 98.99% |
| Test Macro F1 | 99.00% |
| Val Macro F1 (chọn model/early stopping) | 98.83% |
| Độ trễ suy luận | 0,0367 ms/mẫu |
| Độ trễ end-to-end (softmax + TopologyFilter) | 0,0246 ms/mẫu |

Macro F1 theo từng phòng: Bedroom 99.57%, Corridor 99.17%, Bathroom 98.33%
(thấp nhất — ít AP riêng biệt), LivingRoom 98.74%, Kitchen 99.17%.

RoomNetMT — model multi-task được ensemble chọn
(results/g3_multitask/models/room_test_metrics_RoomNetMT.json):

| Chỉ số | RoomNetMT | RoomNetLite (cùng đợt chạy) |
|--------|-----------|------------------------------|
| Test Accuracy | **99.16%** | 98.99% |
| Test Macro F1 | **99.17%** | 99.00% |
| Độ trễ (ms/mẫu) | 0,0193 | 0,0367 |
| Head hoạt động — act_agreement (val) | 97.32% | không có |

K-fold 5-fold (results/after_optimized/kfold_metrics_roomnet.json):
RoomNetLite 97.80% ± 1.06%, khoảng tin cậy 95% [96.88%, 98.73%].

### 8.3. Kết quả phát hiện bất thường (GRU-AE + rules)

Tập test tách riêng D13–D14 (166 sequence, không giao với train D01–D10 và
chọn ngưỡng D11–D12) — results/after_optimized/anomaly_test_metrics.json:

| Chỉ số | Hybrid (AE + Rules) | AE-only |
|--------|---------------------|---------|
| Precision | 100% | — |
| Recall | 99% | — |
| F1 | 99.50% | 98.48% |

Ngưỡng reconstruction error 1.6089 (results/after_optimized/anomaly_threshold.json)
— chọn bằng grid search quantile [0.90–0.995] trên validation D11–D12, không
dùng quantile 0.99 cố định như bản gốc.

Giới hạn: tập test chỉ chứa 2/4 loại bất thường (night_activity,
unusual_transition_pattern) do dữ liệu mô phỏng chỉ đặt anomaly ở 4 ngày cuối
— đã ghi ở mục 10.2.

### 8.4. Phát hiện ngã (Mobile Sensor) — CHƯA KIỂM THỬ

Chưa có số liệu đánh giá: hệ thống chưa được kiểm thử với accelerometer thật
— đây là hạn chế được ghi rõ ở mục 10.2, không có con số nào ở bảng này để
tránh báo cáo sai.

Đã cài đặt (chờ kiểm thử): MobileSensorFusion + MobileSensorMonitor
(src/smarthome/mobile_sensor.py, src/smarthome/inference.py:process_mobile_sensor)
— phát hiện va chạm theo ngưỡng impact_threshold = 18 m/s², theo dõi trạng
thái bất động sau va chạm (still_after_impact_seconds = 5s), cảnh báo
CRITICAL qua /api/sensor và webhook. Kịch bản kiểm thử đề xuất: ngã mô phỏng
trên đệm với 5 người × 10 lần, đối chiếu sensitivity/specificity — hẹn mục
hướng phát triển.

### 8.5. Kích thước model và tài nguyên (đo thật trên máy phát triển)

| Thành phần | Giá trị đo | Nguồn |
|--------|---------|-------|
| RoomNetLite (roomnet_lite.pt) | 49 KB | models/ |
| GRU Autoencoder (gru_autoencoder.pt) | 104,5 KB | models/ |
| SimpleCNN (simple_cnn.pt) | 113,1 KB | models/ |
| Độ trễ suy luận RoomNetLite | 0,0367 ms/mẫu | results/g3_multitask/models/room_test_metrics.json |
| Độ trễ suy luận RoomNetMT | 0,0193 ms/mẫu | results/g3_multitask/models/room_test_metrics_RoomNetMT.json |
| Độ trễ end-to-end (softmax + TopologyFilter) | 0,0246 ms/mẫu | cùng file trên |

Lưu ý thẳng thắn: các số liệu trên đo trên máy phát triển (Windows, CPU
thường), chưa đo trên thiết bị edge (Raspberry Pi/ESP32). Đánh giá tài nguyên
trên thiết bị edge là việc còn lại — xem mục 10.2.

### 8.6. Kiểm thử phần mềm, phân quyền và bảo mật

Ba bộ kiểm tra độc lập, chạy lại được bất cứ lúc nào.

**Bộ test tự động** (`pytest tests -q`): **91 test**, gồm thuật toán (chia tập, tính chỉ số, tiền xử
lý, topology, bộ luật), tích hợp API (đăng ký, đăng nhập, phân quyền theo vai trò, mã chia sẻ, xuất
CSV), và các test hồi quy cho từng lớp bảo mật. Mỗi lớp bảo mật có ít nhất một test chốt hành vi, ví
dụ giới hạn số lần đăng ký theo IP, giới hạn dò mật khẩu, và việc chuyển sang Redis không được làm
mất cấu trúc dự phòng.

**Quét phân quyền** (`scripts/security_sweep.py`): liệt kê toàn bộ route từ URL map rồi gọi **không
kèm phiên đăng nhập**, và gọi thêm một lần với bearer token sai. Kết quả: **39 tổ hợp route và
phương thức trên 34 route `/api/*`, không tổ hợp nào trả dữ liệu**. Bốn endpoint công khai có chủ đích
là đăng nhập, đăng xuất, đăng ký và kiểm tra sức khỏe. Cách quét này ra đời sau khi server được tách
thành các blueprint, vì rủi ro lớn nhất của việc tách module là một endpoint mất trang trí yêu cầu
đăng nhập mà không có gì báo lỗi.

**Quét mã tĩnh** (`scripts/full_security_audit.py`) và bộ soát báo cáo
(`scripts/report_style_check.py`). Lần chạy đầu của bộ quét mã báo 69 vấn đề, nhưng khi kiểm chứng
từng mục thì phần lớn là sai: mẫu nhận diện thuật toán mã hoá cũ khớp cả chữ `DESC` trong `ORDER BY`
và chữ `des` trong `description`; mẫu nhận diện ghi log lộ bí mật khớp mọi dòng có chữ `token`; phần
kiểm tra phụ thuộc chỉ so tên gói nên báo oan cả những gói đã đủ mới. Sau khi sửa bảy lỗi độ chính
xác của chính bộ quét, còn **4 vấn đề, tất cả ở mức thông tin** và đều là thiết kế đã được chấp nhận
và ghi trong tài liệu bảo mật: quảng bá mDNS trong LAN, ngày hết hạn của bộ ghim chứng chỉ, và hai
chỗ cho phép HTTP trong mạng LAN.

Các lỗi bảo mật thật đã tìm và sửa trong quá trình làm được liệt kê ở mục 7, trong đó đáng chú ý
nhất là lớp ghim chứng chỉ của ứng dụng Android. Lớp này tự viết một `X509TrustManager` chỉ kiểm tra
ngày hết hạn của chứng chỉ mà không xác thực chuỗi tới root tin cậy, kèm một bộ kiểm tra tên miền
luôn trả về đúng khi chưa cấu hình ghim. Ở trạng thái mặc định — tệp ghim chỉ có dòng chú thích —
ứng dụng chấp nhận mọi chứng chỉ và mọi tên miền, tức là lớp bảo mật tự tạo ra lỗ hổng. Đã sửa bằng
cách uỷ thác việc xác thực chuỗi cho trust store của hệ thống rồi mới áp ghim, và để nguyên cấu hình
mặc định của Android khi chưa cấu hình ghim. Bản vá được xác nhận bằng cách biên dịch lại toàn bộ
ứng dụng (`assembleDebug` thành công).

### 8.7. Kiểm chứng triển khai

Phần triển khai được kiểm bằng cách chạy thật chứ không chỉ đọc cấu hình. Kết quả:

| Hạng mục | Lệnh | Kết quả |
|---|---|---|
| Cấu hình nginx | `nginx -t` trong container | `configuration file test is successful` |
| Cấu hình Docker Compose | `docker compose config --quiet` | exit 0, cho cả hai tệp compose |
| Điểm vào WSGI | gọi thẳng giao diện WSGI thô | `200 OK` cho `/api/health` |
| Ảnh production | `docker build --target prod` | thành công, gunicorn 26.2.0 và torch 2.15.0+cpu |
| Container chạy | `docker run` | `Up (healthy)`, **0 dòng `[ERROR]`** trong log |
| Worker | log khởi động | `Using worker: gthread`, 2 worker, control socket trong home riêng |
| API sau khi chạy | `GET /api/health` | `200`, `{"status":"ok","database":"ok"}` |
| Header bảo mật | `GET /` | `200`, có `Content-Security-Policy` |
| Bảo vệ SSE | `GET /api/stream` khi chưa đăng nhập | `401` |

Sáu lỗi chặn triển khai đã được phát hiện và sửa ở bước này, trong đó hai lỗi chỉ lộ ra khi chạy
thật: cấu hình nginx khai báo trùng khối `upstream` và dùng một tệp `include` không tồn tại trong ảnh
`nginx:alpine`, còn ảnh production thì chạy máy chủ phát triển của Werkzeug thay vì gunicorn như tệp
compose vẫn ghi. Chi tiết ở `docs/12_trien_khai.md`.

Chưa kiểm chứng được ở máy phát triển: đường Cloudflare Tunnel cần tài khoản và token thật; chứng
chỉ Let's Encrypt cần tên miền trỏ về IP công khai nên lần thử dùng chứng chỉ tự ký; và chưa khởi
động đồng thời cả bốn service trong tệp compose.

## 9. TRIỂN KHAI THỰC TẾ

### 9.1. Đóng gói Docker

Dockerfile multi-stage 4 stage (base / dev / prod / archive): stage prod chạy
Python 3.11-slim, PyTorch CPU-only (requirements-docker.txt), user không phải
root (appuser), HEALTHCHECK gọi /api/health mỗi 30 giây. Build:

```bash
docker build -t an-tam-home:2310 --target prod .
```

### 9.2. docker-compose.prod.yml

Sáu dịch vụ: app (an-tam-home:2310, không expose port ra ngoài), nginx
(reverse proxy + SSL termination, port 80/443), redis (rate limit / cache dùng
chung khi chạy nhiều worker, persistence appendonly), certbot (Let's Encrypt,
profile ssl), certbot-init (cấp chứng chỉ lần đầu, profile ssl-init),
cloudflared (Cloudflare Tunnel, profile tunnel, token từ biến môi trường
CLOUDFLARE_TUNNEL_TOKEN). Volume ./data và ./models mount vào app để dữ liệu
SQLite và model không nằm trong container.

### 9.3. HTTPS và tên miền — hai phương án

- **Let's Encrypt + Nginx**: đặt DOMAIN và CERTBOT_EMAIL trong .env, chạy
  `docker compose -f docker-compose.prod.yml --profile ssl-init run certbot-init`,
  rồi bật profile ssl (certbot renew tự động 12 giờ/lần).
- **Cloudflare Tunnel** (không mở port, không cần chứng chỉ công khai): tạo
  tunnel trên dashboard Cloudflare, đặt CLOUDFLARE_TUNNEL_TOKEN vào .env, chạy
  `--profile tunnel`; trỏ tên miền đến tunnel trong dashboard. Cookie phiên tự
  bật Secure khi server chạy HTTPS (app.py — secure_cookie_requested).

### 9.4. Cấu hình Android cho production

- URL server: dùng tên miền HTTPS thay cho http://IP-LAN.
- Certificate pinning: ghim SPKI SHA-256 của chứng chỉ (từ cert_pins.txt);
  luân chuyển pin trước hạn hết (network_security_config.xml, expiration
  2027-11-01) — quy trình ở SECURITY.md mục 1.6.
- Trong LAN vẫn dùng NSD (_antam._tcp) tự tìm server qua HTTP — thiết kế có
  chủ đích, đã ghi trong SECURITY.md §1.6.

### 9.5. Kiểm tra sau triển khai

```bash
curl https://<domain>/api/health   # {"status":"ok","database":"ok",...}
```

Lưu ý: rate limit nằm trong RAM từng tiến trình — chạy một worker là cấu hình
được hỗ trợ; nếu chạy nhiều worker, chuyển bộ đếm sang Redis (đã có trong
compose) — xem mục 10.3.

## 10. KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN

### 10.1. Tóm tắt thành quả

1. **Định vị mức phòng** đạt 98.99% test accuracy với RoomNetLite và 99.16%
   với RoomNetMT (results/g3_multitask/models/room_test_metrics*.json, seed 42)
2. **Ensemble meta-learning** chọn model theo từng bộ dữ liệu trên validation,
   không dùng tập test (scripts/train_ensemble.py, model_choice.json)
3. **Phát hiện bất thường** bằng GRU-AE: hybrid AE+Rules F1 99.50% trên tập
   test tách riêng D13–D14 (results/after_optimized/anomaly_test_metrics.json)
4. **Head hoạt động** của RoomNetMT đồng thuận 97.32% với bộ luật trên
   validation (roomnet_mt_val_metrics.json)
5. **Bảo mật**: khóa session ngẫu nhiên, hạn mức tần suất theo nhóm endpoint,
   JSON-only guard, CSP/nosniff/X-Frame-Options, băm BSSID SHA-256; lớp ghim
   chứng chỉ Android đã được vá sau khi phát hiện lỗi khiến nó tự vô hiệu; quét
   phân quyền 39 tổ hợp route không hở; quét mã tĩnh sau khi sửa chính bộ quét
   còn 4 mức thông tin (SECURITY.md và mục 8.6)
6. **Hạn mức tần suất phân tán**: bộ đếm dùng chung qua Redis khi đặt
   `REDIS_HOST`, gộp thành một script Lua nguyên tử. Đo trên Redis thật: 60
   request đồng thời với ngưỡng 10 cho qua đúng 10 (bản đọc-rồi-ghi cho qua 29),
   và hai tiến trình cộng dồn đúng vào một hạn mức (mục 7.6)
7. **Triển khai**: Docker multi-stage, gunicorn worker `gthread` cho SSE,
   docker-compose.prod (Nginx/certbot/Cloudflare Tunnel/Redis), PWA dashboard,
   NSD tự tìm server; đã chạy thật và sửa 6 lỗi chặn khởi động (mục 8.7)

### 10.2. Hạn chế hiện tại

- **Chưa có dữ liệu RSSI thực tế** — toàn bộ số liệu đo trên dữ liệu mô phỏng
  v2; hạn tuần 9–10 của đề cương đã qua, đây là việc bắt buộc còn lại.
- **Phát hiện ngã chưa kiểm thử** với accelerometer thật (mục 8.4).
- **Chưa đo trên thiết bị edge** (Raspberry Pi/ESP32); số hiệu năng hiện tại
  đo trên máy phát triển.
- **Độ chính xác từng phòng chưa đồng đều**: Bathroom F1 98.33% (thấp nhất)
  do ít AP riêng biệt.
- **Trạng thái khác vẫn nằm trong RAM từng tiến trình**: hạn mức tần suất đã
  chuyển được sang Redis, nhưng trạng thái cảm biến chuyển động, lịch sử suy luận
  tạm thời và tiến độ huấn luyện thì chưa. Muốn chạy nhiều instance thật vẫn phải
  ghim mỗi căn nhà vào một instance, hoặc chuyển nốt các phần đó.
- **Test anomaly** chỉ chứa 2/4 loại bất thường.
- **Android collector** chưa chạy end-to-end trên thiết bị thật.

### 10.3. Hướng phát triển

Đã thực hiện trong khuôn khổ khóa luận: Docker multi-stage, docker-compose.prod
(Nginx + certbot + Cloudflare Tunnel + Redis), certificate pinning Android,
hạn mức tần suất nhiều tầng và bản phân tán dùng chung qua Redis. Các hướng dưới
đây là phương án **nếu** có thời gian và điều kiện **có thể** triển khai tiếp:

| Ngắn hạn (nếu tiếp tục phát triển) | Trung hạn (có thể làm sau khóa luận) | Dài hạn (cần nguồn lực) |
|----------------------|------------------------|-------------------|
| **Server chung nhiều gia đình**: schema đã hỗ trợ nhiều tài khoản/nhà trên một máy chủ; nếu mở rộng cần bảng gói dịch vụ và phân cách tài nguyên | **Lưu trữ phân tán (phần còn lại)**: hạn mức tần suất đã dùng Redis; còn phiên đăng nhập và lịch sử suy luận, cùng việc đưa model artifact lên S3/MinIO | Federated learning giữa các nhà (privacy-preserving) |
| Chuyển nốt trạng thái cảm biến và lịch sử suy luận sang Redis để chạy nhiều instance mà không cần ghim mỗi nhà vào một instance | **Backup tự động**: sqlite backup API + đồng bộ lên node phụ (rclone/scp) | Radar mmWave phát hiện ngã không cần điện thoại |
| K-fold cho RoomNetMT; thu dữ liệu RSSI thực tế (việc bắt buộc còn lại) | Multi-person tracking (WiFi CSI) | Tích hợp hệ thống y tế (EMR) |
| Thêm cảm biến môi trường (nhiệt độ, độ ẩm) | Auto-retrain khi dữ liệu drift | Dự đoán xu hướng sức khỏe dài hạn |

## 11. TÀI LIỆU THAM KHẢO

1. Wen, Y., Zhang, K., Li, Z., & Qiao, Y. (2016). A Discriminative Feature Learning Approach for Deep Face Recognition. *Computer Vision – ECCV 2016*, LNCS 9911, 499–515. (Cảm hứng cho CenterLoss trong RoomNetLite.)
2. Bahl, P., & Padmanabhan, V. N. (2000). RADAR: An In-Building RF-based User Location and Tracking System. *Proceedings of IEEE INFOCOM 2000*, 775–784. (Nền tảng của WiFi fingerprinting.)
3. Wang, F., Feng, J., Zhao, Y., Zhang, X., Zhang, S., & Han, J. (2019). Joint Activity Recognition and Indoor Localization with WiFi Fingerprints. *IEEE Access*, 7, 80058–80068. Bản công khai: arXiv:1904.04964, https://arxiv.org/abs/1904.04964. Mã nguồn: https://github.com/geekfeiw/ARIL. (Tham khảo cho kiến trúc đa nhiệm RoomNetMT.)
4. Scholl, Z. (2019). FIND3 — Framework for Internal Navigation and Discovery. https://github.com/schollz/find3 (truy cập 2026-10-30). (Tham khảo quy trình learn/track và ý tưởng meta-model.)
5. Goodfellow, I., Bengio, Y., & Courville, A. (2016). *Deep Learning*. MIT Press. ISBN 978-0-262-03561-3.
6. Pedregosa, F., Varoquaux, G., Gramfort, A., et al. (2011). Scikit-learn: Machine Learning in Python. *Journal of Machine Learning Research*, 12, 2825–2830. https://jmlr.org/papers/v12/pedregosa11a.html
7. OWASP Foundation. (2021). *OWASP Top 10:2021 — The Ten Most Critical Web Application Security Risks*. https://owasp.org/Top10/ (truy cập 2026-11-01).
8. Cloudflare. (2026). *Cloudflare Tunnel Documentation*. https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/ (truy cập 2026-11-02).
9. Cho, K., van Merriënboer, B., Gulcehre, C., et al. (2014). Learning Phrase Representations using RNN Encoder–Decoder for Statistical Machine Translation. *EMNLP 2014*. Bản công khai: arXiv:1406.1078, https://arxiv.org/abs/1406.1078. (Nguồn của đơn vị GRU dùng trong bộ phát hiện bất thường.)
10. PyTorch Foundation. (2026). *PyTorch documentation*. https://pytorch.org/docs/ (truy cập 2026-11-02).

*Ghi chú:* các bài hội nghị ở mục 1, 2 và 9 nên bổ sung DOI của nhà xuất bản trước khi nộp chính
thức. Báo cáo này cố ý không ghi DOI khi chưa đối chiếu được với trang của nhà xuất bản, để tránh
đưa vào một mã định danh không kiểm chứng.

## 12. PHỤ LỤC

### Phụ lục A: Cài đặt nhanh (Quick Start)

```bash
# 1. Clone & build
git clone https://github.com/NovPhuc/smart-home-wifi-monitor.git
cd smart-home-wifi-monitor
docker build -t an-tam-home:2310 .

# 2. Chuẩn bị data/models
mkdir -p data models
# Copy model files vào models/

# 3. Cấu hình
cp .env.example .env
# Edit .env với secret key, SSL cert paths

# 4. Chạy
docker run -d -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/models:/app/models \
  -e SMART_HOME_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))") \
  an-tam-home:2310
```

### Phụ lục B: API Reference (Tóm tắt)

| Method | Endpoint | Auth | Mô tả |
|--------|----------|------|-------|
| GET | `/api/health` | Public | Health check |
| POST | `/api/auth/register` | Public | Đăng ký tài khoản |
| POST | `/api/auth/login` | Public | Đăng nhập |
| GET | `/api/auth/me` | Session | Thông tin user hiện tại |
| GET/POST | `/api/homes` | Session | CRUD nhà |
| GET/POST | `/api/rooms` | Owner | CRUD phòng |
| POST | `/api/collect` | Device/Session | Gửi fingerprint (training) |
| POST | `/api/scan` | Device | Gửi WiFi (inference) |
| POST | `/api/sensor` | Device | Gửi gia tốc kế |
| GET | `/api/status` | Session | Trạng thái realtime |
| GET | `/api/history` | Session | Lịch sử dự đoán |
| GET | `/api/alerts` | Session | Danh sách cảnh báo |
| POST | `/api/training/start` | Owner | Bắt đầu train |
| GET | `/api/training/status` | Owner | Tiến độ train |
| POST | `/api/homes/{id}/share` | Owner | Tạo mã chia sẻ 6 số |
| POST | `/api/homes/join` | Public | Tham gia nhà bằng mã |

### Phụ lục C: Troubleshooting

| Vấn đề | Nguyên nhân | Giải pháp |
|--------|-------------|-----------|
| Android không tìm thấy server NSD | Firewall chặn mDNS | Mở port 5353 UDP, tắt VPN |
| Dashboard không cập nhật realtime | SSE blocked by proxy | Cấu hình proxy_buffering off |
| Certificate pinning failed | Pin sai/hết hạn | Cập nhật cert_pins.txt + rebuild APK |
| Model accuracy thấp | Ít AP / dữ liệu ít | Thêm AP, thu thập thêm dữ liệu |
| DB locked | Multiple writers | Kiểm tra WAL mode, singleton DB |

---

**KẾT THÚC BÁO CÁO**

*Báo cáo được viết bởi sinh viên Nguyễn Hồài Phúc. Danh sách người hướng dẫn điền ở trang bìa. Toàn bộ mã nguồn, dữ liệu thử nghiệm và tài liệu kèm theo là kết quả công việc nghiên cứu của khóa luận.*