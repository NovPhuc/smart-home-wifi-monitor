# 10 — Chạy 2 model trên cùng một dự án

Cấu hình theo bản thiết kế trong chat với Claude, đã **cài thật và kiểm chứng thật** trên máy này
ngày 2026‑10‑26.

| | Agent A | Agent B |
|---|---|---|
| Model | **GLM 5.3 Flash** | **DeepSeek V4.1 Flash (suy luận max)** |
| Công cụ | OpenCode 1.19.3 | DeepSeek Harness |
| Thư mục làm việc | `..\wt-glm-flash` | `..\wt-deepseek` |
| Nhánh git | `agent/glm-flash` | `agent/deepseek` |
| Alias qua proxy | `cliproxy/glm-first` | `cliproxy/deep-first` |

## 1. Kiến trúc

```
OpenCode ─┐                                    ┌─→ deepseek-ai/deepseek-v4.1-flash
          ├─→ CLIProxyAPI ─→ nim-limiter ──────┼─→ z-ai/glm-5.3-flash
DSH ──────┘   127.0.0.1:9999   127.0.0.1:9101  └─→ minimaxai/minimax-m3.1-flash
                                                    (NVIDIA NIM, 1 key, 40 req/phút)
```

- **Cùng một proxy, cùng một key NVIDIA, cùng một hạn mức 40 request/phút.** Bộ giới hạn chia
  hạn mức **theo model**: hai agent dùng hai model khác nhau thì mỗi bên được ~20 req/phút khi cả
  hai cùng bận, bên nào rảnh thì dùng hết 40.
- **Proxy ép DeepSeek chạy max**, client không cần gửi gì. Đã kiểm chứng bằng upstream giả:
  body tới NVIDIA có `chat_template_kwargs: {"thinking":true,"reasoning_effort":"max"}` và
  `reasoning_effort: "max"`, còn request tới GLM thì **không** bị thêm gì.

## 2. Đã cài ở đâu

| Thành phần | Đường dẫn |
|---|---|
| Proxy + bộ giới hạn + script | `C:\cliproxy\` |
| Cấu hình OpenCode (dùng chung mọi dự án) | `C:\Users\nguye\.config\opencode\opencode.json` |
| Cấu hình DSH | `C:\Users\nguye\.dsh\profiles\desktop\cordis.patch.yml` |
| Biến môi trường | `CLIPROXY_API_KEY` (User), `NVIDIA_API_KEY` (User) |
| Worktree agent A | `E:\Downloads\smart-home-wifi-monitor2310\wt-glm-flash` |
| Worktree agent B | `E:\Downloads\smart-home-wifi-monitor2310\wt-deepseek` |
| Script mở cả hai | `E:\Downloads\smart-home-wifi-monitor2310\chay-2-agent.ps1` |

Các alias proxy đang phục vụ:

| Alias | Chuỗi |
|---|---|
| `glm-flash` | GLM 5.3 Flash (ghim, không dự phòng) |
| `deepseek` | DeepSeek V4.1 Flash max (ghim, không dự phòng) |
| `minimax` | MiniMax M3.1 Flash |
| `best` | DeepSeek → GLM Flash → MiniMax |
| `glm-first` | GLM Flash → MiniMax |
| `deep-first` | DeepSeek → MiniMax |

## 3. Phát hiện quan trọng: NVIDIA đang treo 2 trong 3 model

Ngày 2026‑10‑26, gọi **thẳng** NVIDIA NIM (không qua proxy, không qua bộ giới hạn):

| Model | Kết quả |
|---|---|
| `minimaxai/minimax-m3.1-flash` | ✅ HTTP 200 sau **1,4 giây** |
| `z-ai/glm-5.3-flash` | ❌ **0 byte** sau 150 giây (thử cả `stream: true` và `stream: false`) |
| `deepseek-ai/deepseek-v4.1-flash` | ❌ **0 byte** sau 200 giây |

Cả hai ID đều **có thật** trong `/v1/models` của chính key này (85 model trả về, có
`z-ai/glm-5.3`, `z-ai/glm-5.3-flash`, `deepseek-ai/deepseek-v4.1-flash`,
`minimaxai/minimax-m3.1-flash`). Nghĩa là key đúng, tên model đúng, nhưng máy chủ NVIDIA nhận kết
nối rồi **không bao giờ trả một byte nào** cho hai model đó.

Đây **không phải lỗi cấu hình** — bản thiết kế của Claude đúng. Nhưng nó làm hỏng đúng kịch bản
mà bạn cần, vì:

> Alias "best" chỉ chuyển model khi upstream trả **lỗi** (429/5xx). Upstream treo thì nó chờ mãi.

### Đã xử lý: cắt treo + cách ly model

Bổ sung vào `C:\cliproxy\nim-limiter.js` (bản gốc của Claude không có):

- `--first-byte-timeout-sec=120` — quá 120 giây mà chưa có header phản hồi thì cắt, trả **504**.
- `--cooldown-sec=180` — model vừa bị cắt bị **cách ly**; request sau cho model đó nhận **503
  ngay lập tức**, nên "best"/"glm-first"/"deep-first" nhảy sang model kế trong vài mili giây.
- `--cooldown-max-sec=3600` — cách ly tăng dần (180s → 360s → 720s → …) khi model chết liên tục,
  để mỗi lần gọi mới không phải trả 120 giây một lần nữa. Model sống lại thì tự xoá cách ly.
- `/healthz` nay trả thêm `firstByteTimeoutSec`, `cooldownSec`, `coolingDownSec`, `strikes`.

**Kết quả đo thật** (upstream giả treo đúng 2 model, chỉ MiniMax sống):

| Lần gọi | Trước khi sửa | Sau khi sửa |
|---|---|---|
| `best` lần 1 | treo vô hạn | **6,1 s** → MiniMax |
| `best` lần 2 | treo vô hạn | **0,0 s** → MiniMax |
| `glm-flash` khi đang cách ly | treo vô hạn | **0,0 s**, HTTP 503 rõ ràng |

**Và đo thật với NVIDIA thật** (`test-models.ps1` sau khi sửa):

```
deepseek   LỖI  120.1s  nim-limiter: deepseek-ai/deepseek-v4.1-flash không trả về byte nào trong 120s
glm-flash  LỖI  120.0s  nim-limiter: z-ai/glm-5.3-flash không trả về byte nào trong 120s
minimax    OK     0.9s  model=minimaxai/minimax-m3.1-flash  "OK"
best       OK     1.0s  model=minimaxai/minimax-m3.1-flash  "OK"
```

Trước khi sửa, `best` sẽ chờ 240 giây rồi vẫn có thể treo. Sau khi sửa: hai model chết bị cách ly,
`best` trả lời trong **1 giây**.

### Hệ quả cho công việc hằng ngày

- Dùng `cliproxy/deep-first` cho DSH và `cliproxy/glm-first` cho OpenCode: hai agent **vẫn chạy
  được việc ngay bây giờ** (rơi về MiniMax M3.1 Flash), và **tự quay lại** DeepSeek/GLM ngay khi
  NVIDIA sửa xong — không phải đổi cấu hình.
- Nếu muốn biết model nào đang chết: `Invoke-RestMethod http://127.0.0.1:9101/healthz` rồi xem
  `coolingDownSec` và `strikes`.
- Nếu NVIDIA chết lâu dài và bạn muốn bỏ hẳn 120 giây chờ đầu tiên: hạ
  `--first-byte-timeout-sec=45` (nhưng đừng thấp hơn 45 vì model suy luận bình thường có thể mất
  ~40 giây mới ra token đầu).

## 4. Một lỗi nữa đã sửa: `start-cpa.ps1` không chạy được trên PowerShell 5.1

`start-cpa.ps1` do Claude giao là UTF‑8 **không có BOM**, trong khi `test-models.ps1` **có** BOM.
Windows PowerShell 5.1 (mặc định của Windows) đọc file `.ps1` không BOM theo bảng mã ANSI, nên
toàn bộ chữ Việt bị đọc sai và script **không parse được**:

```
At C:\cliproxy\start-cpa.ps1:82 char:126
+ ... enCode g ¯?i vAÿo proxy). Ch §­y M ¯~T l §n l ¯Ønh sau r ¯"i ch §­y  ...
Unexpected token 'i' in expression or statement.
```

Đã thêm BOM UTF‑8: script parse OK trên **cả** PowerShell 5.1 và 7.

> Lưu ý: công cụ soạn thảo dùng ở đây **xoá BOM** mỗi lần sửa file. Nếu sau này sửa
> `start-cpa.ps1` bằng editor không giữ BOM, phải thêm lại, nếu không nó lại hỏng trên 5.1.

## 5. Chạy hằng ngày

```powershell
# Cửa sổ proxy (để mở suốt buổi làm việc):
cd C:\cliproxy
.\start-cpa.ps1
#   -> Giới hạn   : tối đa 40 request/phút tới NVIDIA (bộ giới hạn ở cổng 9101)
#   -> Cắt treo   : không có phản hồi đầu sau 120 giây -> trả 504 và cách ly model 180 giây
#   -> CLIProxyAPI chạy tại http://127.0.0.1:9999

# Kiểm tra model nào còn sống (tốn 4 request):
.\test-models.ps1

# Mở cả hai agent, mỗi agent một worktree:
cd E:\Downloads\smart-home-wifi-monitor2310
.\chay-2-agent.ps1
```

Trong OpenCode: `/models` → chọn `cliproxy/glm-first` (mặc định đã đặt sẵn).
Trong DSH: model mặc định đã là `cliproxy/deep-first`, `reasoningEffort: max`.

Hoặc gọi một lệnh không cần giao diện:

```powershell
cd E:\Downloads\smart-home-wifi-monitor2310\wt-glm-flash
opencode run -m cliproxy/glm-first "đọc server/static/app.js và chỉ ra lỗi"
```

## 6. Chia việc và gộp kết quả

Hai agent sửa **hai bản sao khác nhau** của cùng repo (git worktree), nên không bao giờ ghi đè
lên nhau. Gộp khi xong:

```powershell
cd E:\Downloads\smart-home-wifi-monitor2310\smart-home-wifi-monitor
git log --oneline agent/glm-flash      # xem agent A đã làm gì
git log --oneline agent/deepseek       # xem agent B đã làm gì
git merge agent/glm-flash
git merge agent/deepseek               # giải quyết xung đột nếu có
```

Gợi ý chia việc để ít xung đột: giao **hai vùng file khác nhau** cho hai agent, ví dụ một agent
lo `server/` + `src/smarthome/`, agent kia lo `android_collector/` + `docs/` + `scripts/`.

Điểm xuất phát của cả hai worktree là commit `8a8f2b0` (checkpoint gộp giao diện).

## 7. Xử lý sự cố

| Hiện tượng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `Proxy từ chối key (401)` | `CLIPROXY_API_KEY` khác key proxy đang chạy | Đặt lại biến, Ctrl+C cửa sổ proxy rồi chạy lại `start-cpa.ps1` |
| `Không thấy alias 'best'` | Cổng 9999 đang là chương trình khác | `Get-NetTCPConnection -LocalPort 9999 -State Listen` rồi xem tiến trình |
| Treo 120s rồi 504 | NVIDIA đang treo model đó | Bình thường; model đã bị cách ly, lần sau đi thẳng sang MiniMax |
| Dòng `[limiter] ... đang cách ly, trả 503 ngay` | Model chính đang chết | Xem `healthz`; đổi sang alias `minimax` nếu cần chắc chắn chạy được |
| `dsh` báo `stream idle timeout` | Đã đặt `streamIdleTimeoutMs: 1200000` trong hồ sơ `desktop`; nếu vẫn còn thì DSH đang chạy hồ sơ khác | Kiểm tra `%USERPROFILE%\.dsh\profiles\<hồ sơ đang chạy>\cordis.patch.yml` |
| Không muốn dùng proxy | Sửa `model:` trong `cordis.patch.yml` về `nvidia/...` | Nhánh `nvidia` trong cùng file là đường đi thẳng, **không** chia hạn mức và **không** được ép max |

## 8. Tóm tắt những gì khác bản Claude giao

1. `nim-limiter.js`: thêm cắt treo theo byte đầu, cách ly model hỏng, cách ly tăng dần, healthz
   chi tiết hơn. (Bản gốc chỉ giới hạn số request.)
2. `config.yaml`: thêm hai alias `glm-first` và `deep-first` để mỗi agent giữ đúng model chính mà
   vẫn có đường lui.
3. `start-cpa.ps1`: thêm tham số `-FirstByteTimeoutSec`, `-CooldownSec`, `-CooldownMaxSec`; thêm
   BOM UTF‑8 để chạy được trên Windows PowerShell 5.1.
4. `opencode.json`: mặc định `cliproxy/glm-first`, thêm `deep-first`, `glm-first`.
5. `cordis.patch.yml`: model mặc định của DSH đổi từ `deepseek` (ghim) sang `deep-first` (có dự
   phòng); thêm danh sách model.
6. `pi-models.json`: thêm `glm-first`, `deep-first`; thống nhất `contextWindow` của GLM Flash về
   1 000 000 cho khớp các client khác.
7. Worktree + script `chay-2-agent.ps1`.
