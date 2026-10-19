# apkverify: kiểm tra quảng cáo trong APK trước khi gửi MO

MO trả APK về vì ba lý do: **thiếu/sai ID quảng cáo trên Remote Config**, **code thiếu hoặc thừa vị trí quảng cáo**,
và **quảng cáo không load/show**. `apkverify` bắt cả ba trước khi APK rời team dev.

| Lệnh | Kiểm gì | Cần gì |
|---|---|---|
| `apkverify project` | Như `static`, nhưng đọc thẳng source của project Android Studio, không cần APK. Dùng lúc đang code | Project Android, spec `.xlsx`, `admob_id.json`, `config_show_ads.json` |
| `apkverify static` | Spec của MO ↔ Remote Config ↔ APK: đủ ID, đúng ID, đủ config, code có gọi đúng tên vị trí, config đang bật | APK, spec `.xlsx`, file JSON Remote Config |
| `apkverify runtime` | Cài APK lên máy/emulator, đọc log của thư viện quảng cáo trong lúc bạn bấm qua app: vị trí nào đã load, đã show, lỗi gì | Như trên, cộng `adb` và một thiết bị |

Chạy trên Windows, Linux, macOS. `project` giúp bắt lỗi sớm; **trước khi gửi MO vẫn chạy `static` trên APK release**,
vì source không cho thấy code R8 đã xoá, flavor nào được build, hay bản build có mới nhất không.

## Cài đặt

Cần [uv](https://docs.astral.sh/uv/). Mỗi máy dev cài một lần:

```bash
uv tool install git+https://github.com/duylt-dev/VerifyTool
```

Cập nhật bản mới: `uv tool upgrade apkverify`. Nếu gõ `apkverify` báo không có lệnh, chạy `uv tool update-shell` rồi mở
lại terminal.

Kiểm tra lúc chạy cần thêm `adb` (Android SDK platform-tools) trên `PATH`, hoặc biến `ANDROID_HOME`.

Phát triển chính tool này: trong thư mục repo chạy `uv sync`, rồi `uv run apkverify …`.

## Kiểm tra project Android (không cần APK)

Mở **Terminal** trong Android Studio (đang ở thư mục project) và gõ:

```bash
apkverify project
```

Tool tìm project (thư mục có `settings.gradle(.kts)`), in package và version đọc được, rồi hỏi 3 câu:

```
1/3 Đường dẫn file admob_id.json (giá trị Remote Config key admob_id): 
2/3 Đường dẫn file config_show_ads.json (giá trị Remote Config key config_show_ads): 
3/3 Đường dẫn file spec quảng cáo của MO (.xlsx): 
```

Kéo-thả file vào terminal hoặc dán đường dẫn đều được. Tên file không quan trọng (`admob_id (1).json` vẫn được hiểu là
key `admob_id`); đưa file template tải từ Firebase console cho cả hai câu đầu cũng được. Lần sau, Enter để dùng lại
đường dẫn lần trước.

Báo cáo ghi vào `build/apkverify/` trong project (thư mục `build/` vốn đã bị git bỏ qua). Exit code giống `static`.
Chạy trong CI thì truyền đủ cờ, tool không hỏi:

```bash
apkverify project --admob-id admob_id.json --config-show-ads config_show_ads.json --spec spec.xlsx
```

Tool đọc chuỗi trong code `.kt`/`.java` của mọi module (bỏ comment, bỏ code test và debug), `applicationId`/`versionName`
trong `build.gradle(.kts)`, App ID trong `AndroidManifest.xml`, và `app/src/main/assets/*.txt`. Giá trị Gradle được tính
bằng code (không viết thẳng) thì tool báo cảnh báo `PRJ-UNRESOLVED` và bỏ qua phần so sánh liên quan.

## Chuẩn bị `input/`

```
input/
├── <app>-release.apk               # đúng bản sẽ gửi MO
├── <spec của MO>.xlsx              # file spec quảng cáo MO gửi
├── admob_id.json                   # giá trị Remote Config key admob_id
└── config_show_ads.json            # giá trị Remote Config key config_show_ads
```

Remote Config đưa vào một trong hai cách:

- mỗi key một file `<key>.json`, nội dung là đúng giá trị của key đó trên Firebase;
- hoặc file template tải từ Firebase console (Remote Config → menu ⋮ → *Download current config file*).

Mỗi lần chỉ để **một** APK và **một** file `.xlsx` trong `input/`, hoặc chỉ rõ bằng `--apk` / `--spec`.

## Kiểm tra tĩnh

```bash
uv run apkverify static
```

Terminal in kết luận `ĐẠT` / `KHÔNG ĐẠT`, các lỗi, và đường dẫn báo cáo HTML trong `output/`. Exit code `1` khi
có lỗi, nên gắn được vào CI.

Báo cáo có:

- danh sách lỗi (`ERROR`: APK không đạt), cảnh báo (`WARN`: cần người xem) và thông tin (`INFO`);
- bảng từng vị trí trong spec: ID trên Remote Config, config bật/tắt, code có gọi tên vị trí không;
- cột "Ghi chú AD" của spec làm checklist khi test tay.

## Kiểm tra lúc chạy

```bash
uv run apkverify runtime --fresh
```

Tool cài APK, tắt app nếu đang mở (để mở lại từ đầu, chạy cả quảng cáo splash), xoá log, rồi mở app. Bạn bấm qua các màn (splash, language, onboard, home, …); mỗi sự kiện quảng cáo hiện
ngay trên terminal. Bấm **Enter** (hoặc Ctrl+C) khi xong, tool ghi báo cáo vào `output/`.

- `--fresh` xoá dữ liệu app trước khi mở, để các màn chỉ hiện lần đầu (language, onboard) chạy lại.
- **Nên dùng emulator.** AdMob luôn trả quảng cáo test trên emulator. Trên máy thật, máy phải được đăng ký
  test device trong AdMob trước khi bấm vào quảng cáo, nếu không tài khoản có thể bị tính invalid traffic.

## Tài liệu

- [`confirm.md`](confirm.md): các quyết định và câu hỏi còn mở.
