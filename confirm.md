# confirm.md: quyết định của `apkverify`

Ba loại mục:

- **`Dn`**: user đã chốt. Không hỏi lại, không đề xuất lại, trừ khi user mở lại.
- **`An`**: mặc định do Claude chọn. Được đổi khi có số đo hoặc yêu cầu mới; ghi lý do vào đây khi đổi.
- **`On`**: còn mở. Phần nào phụ thuộc vào câu trả lời thì chưa làm; phần độc lập vẫn làm.

Mọi số đo ghi kèm ngày, máy và input. Máy đo: Apple M2 Pro, 32 GB RAM, macOS (Darwin 27).

---

## Đã chốt (D)

| # | Quyết định | Ngày |
|---|---|---|
| D1 | Mục đích: verify APK **trước khi gửi MO**, bắt đúng ba lý do MO trả APK: (a) thiếu/sai ID quảng cáo trên Remote Config (Firebase), (b) code thiếu hoặc thừa vị trí quảng cáo so với spec, (c) quảng cáo không load/show. Lần trả gần nhất: "miss id, quảng cáo không load/show". | 2026-10-05 |
| D2 | Viết bằng **Python**, không C++. Chạy được trên Windows, Linux, macOS. | 2026-10-05 |
| D3 | Đầu vào là **APK release** (đúng thứ MO nhận). Không quét source code. **Sửa bởi D11:** quét source được thêm làm bước kiểm sớm; APK release vẫn là bước cuối trước khi gửi MO. | 2026-10-05, sửa 2026-10-19 |
| D4 | "Chuẩn" để so là **file spec xlsx của MO**, layout như `Quang_cao_Ads_Spin_wheel_2.xlsx` (một dòng tiêu đề cột: STT, Task, Trạng thái, Định Dạng, Config Name, Ad Space, Network Ad Name, ID, Ghi chú AD, Mã task, Link ClickUp). | 2026-10-05 |
| D5 | Giao diện: **CLI + báo cáo HTML**, exit code khác 0 khi có lỗi (để gắn CI sau). Bản đầu không có GUI. | 2026-10-05 |
| D6 | File đầu vào đặt trong **`input/`**; báo cáo HTML ghi vào **`output/`**. | 2026-10-05 |
| D7 | Kiểm tra lúc chạy là **bán tự động**: tool cài APK qua adb và đọc log; người test tự bấm qua app. | 2026-10-05 |
| D8 | Bộ khung `.claude/` của `fbdl` được viết lại cho dự án này. Các skill mobile được giữ nhưng ghi là không dùng; `mobile-development` chuyển sang dùng. Bản backup: `~/Desktop/VerifyTools-scaffold-backup-20261005-1609.zip`. | 2026-10-05 |
| D9 | Git: chỉ commit code, test, `README.md`, `confirm.md` và cấu hình dự án. Công cụ AI và tài liệu cho AI (`.claude/`, `LLM.md`, `AGENTS.md`, `docs/`, `plans/`) chỉ nằm trên máy, git-ignored, và đã được xoá khỏi lịch sử trước lần push đầu. Thay bản 2026-10-05, khi các file này còn được commit. | 2026-10-19 |
| D10 | Code chia theo ba bước **Input → Process → Output**: `src/apkverify/input/` (đọc file, APK, log thiết bị), `process/` (kiểm tra thuần), `output/` (terminal, báo cáo HTML), ở gốc package; phần runtime cũng chia theo ba bước. Đợt tách chỉ đổi cấu trúc, không đổi hành vi. | 2026-10-19 |
| D11 | Thêm lệnh **`apkverify project`**: chạy kiểm tra tĩnh trên source của project Android Studio, không cần APK. Dev chạy trong Terminal của Android Studio; tool hỏi 3 câu (đường dẫn `admob_id.json`, `config_show_ads.json`, spec `.xlsx`) cho câu nào chưa có cờ. Đây là chế độ **thêm**: `apkverify static` trên APK release vẫn là bước cuối trước khi gửi MO, vì source không cho thấy code R8 đã xoá, flavor nào được build hay bản build có mới không. | 2026-10-19 |
| D12 | Phát hành cho dev: **cài một lần mỗi máy** bằng `uv tool install git+https://github.com/duylt-dev/VerifyTool`, rồi gõ lệnh trong Terminal của Android Studio. Không copy tool vào repo Android, không Gradle task. | 2026-10-19 |

## Mặc định của Claude (A)

| # | Mặc định | Lý do |
|---|---|---|
| A1 | Python `>=3.11`, `.python-version` = 3.13, quản lý bằng `uv`. | 3.11 có sẵn wheel cho cả ba hệ điều hành; 3.13 là bản trên máy dev. |
| A2 | Dependency chạy: `openpyxl` (đọc spec), `androguard` (manifest + resources của APK), `jinja2` (HTML), `loguru` (chỉ để tắt log của androguard). DEX được đọc bằng module riêng `input/dex_strings.py`, không qua androguard. | Đo 2026-10-05 trên `SpinWheel2_dev_1.0.1-release.apk` (43 MB, 3 DEX): module riêng đọc 126 946 chuỗi trong 0,08 s. Bộ phân tích DEX của androguard dựng cả cây lớp, chậm hơn nhiều mà tool chỉ cần bảng chuỗi. `loguru` được khai báo từ 2026-10-19: `input/apk_reader.py` import trực tiếp, trước đó chỉ có nhờ androguard kéo theo, nên một bản androguard bỏ `loguru` sẽ làm tool hỏng lúc import. |
| A3 | Nguồn Remote Config bản đầu là **file JSON trong `input/`**, hai dạng: (a) mỗi tham số một file `<key>.json` (như `admob_id.json`, `config_show_ads.json`), (b) file template Firebase tải từ console (có khoá `parameters`). Gọi thẳng Firebase là O1. | Chưa có service account. |
| A4 | Thư viện quảng cáo của team đọc 4 key Remote Config: `admob_id`, `pangle_id`, `gam_id` (danh sách ad unit) và `config_show_ads` (bật/tắt từng vị trí). Key rỗng thì đọc `assets/<key>.txt`. | Đọc từ code APK (jadx, 2026-10-05): lớp khởi tạo gán `listOf("admob_id","pangle_id","gam_id")` và `"config_show_ads"`; listener của `fetchAndActivate` đọc `assets/<key>.txt` khi giá trị rỗng. Thêm 2026-10-19 (đọc source trên máy): bản binary `com.github.piontech96:Dolphin-Ads` (AR-Dog, Roblox-Skin) chứa các key trong thư viện, còn tên vị trí kể cả pool `preload_Interstitial_ID1/ID2` do app truyền vào; bản source `LibAds` (Love-Test) đặt giá trị mặc định từ `res/raw/<key>.txt` qua `setDefaultsAsync`, không đọc `assets/`, nên app dùng bản này luôn nhận APK-FALLBACK-EMPTY. |
| A5 | So tên **đúng từng ký tự, phân biệt hoa thường**; khi lệch thì gợi ý tên gần nhất (`difflib`). | Key Remote Config và `spaceName` được so bằng `equals` trong thư viện. Spec có sẵn tên lệch hoa thường (`Language1.2_native1` / `Am_language1.2_native1`) và lỗi chính tả (`language2.1_naitve`); dev phải gõ đúng như spec. |
| A6 | Bảng ánh xạ "Định Dạng" của spec sang `adsType` của thư viện: Native → `native`; Interstitial → `interstitial`; Open Ad → `open_app`; Native Full Screen → `native_full_screen` hoặc `native_interstitial`; Banner Adapt → `banner_adaptive` hoặc `picture_in_picture`. | Spec Spin Wheel 2 ghi "Native Full Screen" cho cả hai loại native toàn màn và "Banner Adapt" cho QC PiP; Remote Config phân biệt. |
| A7 | "Code có gọi vị trí" = tên `configName`/`spaceName` có trong bảng chuỗi DEX. **Không** dò "thừa" trong code bằng heuristic; "thừa" được bắt ở Remote Config (tĩnh) và ở log lúc chạy. | Đo 2026-10-05 trên APK Spin Wheel 2: regex theo hậu tố (`_native`, `_adaptive`…) cho 476 ứng viên, hầu hết là chuỗi SDK; lọc theo tiền tố `configName_` còn 35, vẫn đa số là chuỗi của SDK (`splash_ad`, `splash_switch`…). Báo động giả nhiều như vậy làm người dùng bỏ qua cả báo cáo. |
| A8 | Mức độ: **ERROR** (APK không đạt), **WARN** (cần người xem), **INFO**. Exit code: `0` không có ERROR, `1` có ERROR, `2` lỗi đầu vào/cách dùng, `130` bị ngắt. | CI chỉ cần biết đạt hay không. |
| A9 | Thông điệp CLI và báo cáo HTML bằng **tiếng Việt**; tài liệu cho AI (`LLM.md`, `docs/`) bằng tiếng Anh. | Người đọc báo cáo là dev và MO; tài liệu kỹ thuật giữ như bộ khung cũ. |
| A10 | Tên báo cáo: `output/<package>_<versionName>_<YYYYMMDD-HHMMSS>_<static|runtime>.html`. Không ghi đè báo cáo cũ. | Giữ lịch sử từng lần kiểm. |
| A11 | Kiểm tra lúc chạy ưu tiên **emulator**. Máy thật phải được đăng ký test device trên AdMob. | AdMob luôn trả quảng cáo test trên emulator, nên không có rủi ro invalid traffic. Chạy APK release với ID thật trên máy chưa đăng ký có thể làm tài khoản bị tính invalid traffic. |
| A12 | `input/` và `output/` không commit. | Chứa APK 43 MB, ID thật và báo cáo từng lần chạy. |
| A13 | Phát hành bằng `uv`: dev cài theo D12 (`uv tool install git+…`), người phát triển tool dùng `uv run apkverify …`. Gói một file chạy (PyInstaller) để sau. | Ít bước nhất để có tool chạy được; androguard kéo theo ~37 package nên gói một file cần đo kích thước trước. Đo 2026-10-19: `uv tool install` từ thư mục dự án cài xong lệnh `apkverify` chạy được từ trong project AR-Dog, báo cáo HTML (template đóng gói kèm) ghi đúng. |
| A14 | `apkverify project` đọc project như sau: project là thư mục gần nhất, từ thư mục hiện tại đi lên, có `settings.gradle(.kts)`; quét mọi module trong `include(...)` và mọi source set trừ `test*`, `androidTest*`, `*Test`, `debug`, `*Debug`; bỏ comment; chỉ đọc giá trị Gradle viết dạng literal; package chỉ coi là biết khi mọi `applicationId` giống nhau và không có `applicationIdSuffix` ngoài block debug; App ID khai báo ngoài `main` hoặc khác nhau giữa các source set cũng không coi là biết; mọi trường hợp đó báo PRJ-UNRESOLVED và bỏ qua check phụ thuộc; App ID `@string/x` tra trong `res/values/*.xml`; thư viện binary nhận diện qua bảng `formats.AD_LIBRARIES`. | Đo 2026-10-19 trên 3 project Pion (AR-Dog, Love-Test, Roblox-Skin): đọc xong trong 0,17–0,34 s, ra đúng package, version, App ID, Firebase project. Chạy cùng spec và Remote Config, `project` trên source và `static` trên APK release cho cùng danh sách lỗi (AR-Dog 46, Roblox-Skin 127) và cùng bảng vị trí, chỉ khác gợi ý "Gần giống" (static-check-spec §9.1). |
| A15 | Báo cáo của `apkverify project` ghi vào `<project>/build/apkverify/`, kèm `last-inputs.json` nhớ 3 đường dẫn lần trước (Enter để dùng lại). Ngoài thư mục đó tool không ghi gì vào project. Không có terminal (CI) mà thiếu cờ thì báo lỗi exit 2, không treo chờ nhập. | `build/` đã được git-ignore ở cả 3 project, nên báo cáo không lọt vào commit; `./gradlew clean` xoá cả báo cáo lẫn `last-inputs.json`. |

## Còn mở (O)

| # | Câu hỏi | Ảnh hưởng |
|---|---|---|
| O1 | Ai cấp được service account quyền *Firebase Remote Config Viewer* cho từng Firebase project? | Có quyền thì tool lấy Remote Config trực tiếp (đúng giá trị đang chạy) thay vì file export tay. |
| O2 | Có cần nhận file AAB không? | Có thì thêm bước chuyển AAB → APK bằng `bundletool`. |
| O3 | `admob_id.json` và `config_show_ads.json` trong `input/` có đúng là giá trị đang chạy trên Firebase không, và có giá trị theo điều kiện (version app, quốc gia…) không? | Nếu có điều kiện, kết quả chỉ đúng với giá trị mặc định. **Bằng chứng 2026-10-05** (emulator, runtime-check-spec §7): 7 config có `isOn=false` trong file vẫn load và show khi chạy thật. Hoặc file không phải giá trị đang chạy, hoặc thư viện bỏ qua `isOn`. Cho tới khi rõ, cảnh báo RC-CONFIG-OFF chỉ đúng với file đã đưa vào. |
