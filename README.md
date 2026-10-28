# BARO

Bộ gõ tiếng Việt cho Linux, lấy cảm hứng từ EVKey. BARO chạy như một **IBus engine**
nên hoạt động trên GNOME, KDE, X11 và Wayland, với Telex và VNI.

> Repo `lamquangminh/EVKey` chỉ chứa phần UI/updater Windows (`evkau`) và binary;
> phần lõi gõ không có trong repo. BARO là bản viết lại engine từ đầu cho Linux,
> giữ hành vi quen thuộc: gõ tắt dấu, khôi phục từ không hợp lệ, Telex/VNI.

## Tính năng

- Telex: `aa ăw ee oo ow uw dd`, dấu `s f r x j`, xoá dấu `z`, `[` = ơ, `]` = ư
- VNI: dấu `1 2 3 4 5`, `6 7 8 9`, xoá dấu `0`
- Đặt dấu thanh theo kiểu **hiện đại** (hoà, thuỷ) hoặc **cổ điển** (hòa, thủy)
- Tự khôi phục từ không hợp lệ về đúng phím đã gõ (`asd` → `asd`)
- Giữ nguyên chữ hoa/thường
- Chuyển Việt/Anh bằng `Ctrl + \`` hoặc menu IBus
- Cấu hình bằng app GTK4: `baro-settings`

## Cài đặt

```bash
cd ~/baro
./install.sh
```

Sau đó chọn **BARO** bằng `Super + Space` (hoặc Settings → Keyboard → Input Sources).

Engine và cấu hình nằm trong thư mục user (`~/.local/lib/baro`, `~/.config/baro`).
Riêng file component phải nằm ở `/usr/share/ibus/component/baro.xml` vì IBus 1.5.34
không quét thư mục component của user; `install.sh` sẽ hỏi quyền root qua `pkexec`
để cài đúng một file XML này.

Nếu phiên đang dùng Fcitx5 (`GTK_IM_MODULE=fcitx`) thì Fcitx5 đang giữ tên D-Bus
`org.freedesktop.IBus`, nên IBus/BARO không thể chạy song song. Chạy:

```bash
im-config -n ibus
```

rồi đăng xuất/đăng nhập lại. Muốn quay lại Fcitx5/Funput: `im-config -n fcitx5`.

## Gỡ

```bash
./uninstall.sh
```

## Phát triển

```bash
python3 -m unittest discover -s tests -v
```

Cấu trúc:

- `baro/core.py` — chuyển đổi Telex/VNI, kiểm tra âm tiết, đặt dấu
- `baro/engine.py` — IBus engine, preedit, phím tắt
- `baro/config.py` — đọc/ghi `~/.config/baro/settings.json`
- `bin/baro-settings` — cửa sổ cấu hình GTK4

## Giới hạn hiện tại

- Chưa có bảng gõ tắt/macro, chính tả, hoặc kiểm tra từ ghép như EVKey.
- Chưa hỗ trợ gõ tắt bằng phím số của Telex (Telex + VNI chỉ chọn một kiểu).
- Preedit hiển thị trong ô nhập; một số ứng dụng có thể vẽ gạch chân.
