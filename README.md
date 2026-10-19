# apkverify: kiểm tra quảng cáo trong APK trước khi gửi MO

MO trả APK về vì ba lý do: **thiếu/sai ID quảng cáo trên Remote Config**, **code thiếu hoặc thừa vị trí quảng cáo**,
và **quảng cáo không load/show**. `apkverify` bắt cả ba trước khi APK rời team dev.

| Lệnh | Kiểm gì | Cần gì |
|---|---|---|
| `apkverify static` | Spec của MO ↔ Remote Config ↔ APK: đủ ID, đúng ID, đủ config, code có gọi đúng tên vị trí, config đang bật | APK, spec `.xlsx`, file JSON Remote Config |
| `apkverify runtime` | Cài APK lên máy/emulator, đọc log của thư viện quảng cáo trong lúc bạn bấm qua app: vị trí nào đã load, đã show, lỗi gì | Như trên, cộng `adb` và một thiết bị |

Chạy trên Windows, Linux, macOS.

## Cài đặt

Cần [uv](https://docs.astral.sh/uv/). Lần đầu, trong thư mục dự án:

```bash
uv sync
```

Kiểm tra lúc chạy cần thêm `adb` (Android SDK platform-tools) trên `PATH`, hoặc biến `ANDROID_HOME`.

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
- [`docs/static-check-spec.md`](docs/static-check-spec.md): từng mã lỗi của kiểm tra tĩnh và cách tool đọc spec,
  Remote Config, APK.
- [`docs/runtime-check-spec.md`](docs/runtime-check-spec.md): kiểm tra lúc chạy.
- [`LLM.md`](LLM.md): cấu trúc code (cho người và AI sửa tool).
