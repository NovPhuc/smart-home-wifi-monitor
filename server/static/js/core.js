/* =============================================================================
 * An Tâm Home — lõi dùng chung
 * -----------------------------------------------------------------------------
 * Chứa hằng số, state toàn cục, tiện ích DOM, hiệu ứng, lớp gọi API và trạng
 * thái nút. Không import module nào khác để mọi module tính năng có thể dùng
 * mà không tạo vòng lặp import.
 * ========================================================================== */

/* ---------------------------------------------------------------- hằng số -- */
export const POLL_MS = 2000;            // nhịp hỏi /api/status khi tab đang mở
export const STREAM_RETRY_MS = 15000;   // thử mở lại SSE sau khi mất kết nối
export const REQUEST_TIMEOUT_MS = 8000; // quá hạn thì hủy để không xếp hàng request
export const STALE_AFTER_S = 15;        // dữ liệu cũ hơn mức này coi như mất kết nối
export const DEMO_STEP_MS = 900;
export const HISTORY_LIMIT = 12;
export const ALERT_LIMIT = 6;

export const DEMO_ROOM_NAMES = {
  Bedroom: 'Phòng ngủ', Corridor: 'Hành lang', Bathroom: 'Phòng tắm',
  LivingRoom: 'Phòng khách', Kitchen: 'Nhà bếp'
};

export const ACTIVITY = {
  CALIBRATING: ['Đang hiệu chuẩn', 'Cần vài mẫu tín hiệu đầu tiên', 'CAL'],
  STILL: ['Đang nghỉ ngơi', 'Không ghi nhận biến động đáng kể', 'YÊN'],
  LIGHT_ACTIVITY: ['Hoạt động nhẹ', 'Tín hiệu thay đổi nhẹ trong phòng', 'NHẸ'],
  MOVING: ['Đang di chuyển', 'Phát hiện biến động tín hiệu Wi-Fi', 'ĐI'],
  ROOM_CHANGE: ['Vừa chuyển phòng', 'Đã xác nhận thay đổi vị trí', 'ĐỔI']
};

export const SAFETY_COPY = {
  NORMAL: ['AN TOÀN', 'OK', 'Sinh hoạt bình thường'],
  WARNING: ['CẦN CHÚ Ý', '!', 'Có dấu hiệu cần kiểm tra'],
  CRITICAL: ['KHẨN CẤP', '!!', 'Phát hiện bất thường nghiêm trọng'],
  COLLECTING: ['ĐANG GOM MẪU', 'OK', 'Hệ thống sẵn sàng'],
  NO_DATA: ['CHƯA CÓ DỮ LIỆU', 'OK', 'Hệ thống sẵn sàng']
};

export const SIGNAL_COPY = { GOOD: 'Tín hiệu tốt', FAIR: 'Tín hiệu vừa', WEAK: 'Tín hiệu yếu' };
export const SENSOR_COPY = {
  MOVING: 'Đang di chuyển', STILL: 'Đang đứng yên',
  IMPACT_RECORDED: 'Ghi nhận va chạm', NO_DATA: 'Chưa có dữ liệu'
};

/* ---------------------------------------------------------- trạng thái ------ */
export const state = {
  authenticated: false,
  me: null,
  rooms: [],
  devices: [],
  calibration: null,
  demoMode: false,
  lastRoom: null,
  lastSafety: null
};

/**
 * Các module tự đăng ký hàm dừng của mình. Nhờ vậy `showAuth` chỉ cần gọi
 * `stopAllActivity()` mà không phải import ngược module dashboard/demo/training.
 */
const stopCallbacks = new Set();

export function registerStop(callback) {
  stopCallbacks.add(callback);
}

export function stopAllActivity() {
  stopCallbacks.forEach(callback => {
    try {
      callback();
    } catch (error) {
      console.error('[An Tâm] lỗi khi dừng hoạt động:', error);
    }
  });
}

/* ------------------------------------------------------------ tiện ích ------ */
export const $ = id => document.getElementById(id);

/** Gắn sự kiện an toàn: bỏ qua nếu phần tử không có trên trang hiện tại. */
export function on(id, type, handler) {
  const element = typeof id === 'string' ? $(id) : id;
  if (element) element.addEventListener(type, handler);
  return element;
}

export const REDUCED_MOTION = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;

/** localStorage có thể bị chặn (Safari riêng tư) — không được làm chết app. */
export const storage = {
  get(key) { try { return localStorage.getItem(key); } catch { return null; } },
  set(key, value) { try { localStorage.setItem(key, value); } catch { /* bỏ qua */ } }
};

/** crypto.randomUUID chỉ có trên HTTPS/localhost; LAN HTTP phải có đường lui. */
export function makeDeviceId(prefix) {
  const random = globalThis.crypto?.randomUUID?.()
    || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
  return `${prefix}-${random}`;
}

export const deviceId = storage.get('an-tam-device-id') || makeDeviceId('phone');
storage.set('an-tam-device-id', deviceId);

export const escapeHTML = value => String(value ?? '').replace(/[&<>'"]/g, c => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]
));

export const roomLabel = name => DEMO_ROOM_NAMES[name] || name || 'Chưa xác định';

export const fmtTime = ts => ts
  ? new Date(ts * 1000).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
  : '—';

export function fmtDuration(minutes) {
  if (minutes == null) return '—';
  if (minutes < 1) return `${Math.round(minutes * 60)} giây`;
  if (minutes < 60) return `${minutes.toFixed(1)} phút`;
  return `${Math.floor(minutes / 60)}g ${Math.round(minutes % 60)}p`;
}

/** Bản dịch lý do cảnh báo — giữ đủ mẫu của app-v2.js (app-v3.js đã làm rơi 3 mẫu). */
export function translateReason(reason) {
  return String(reason || '')
    .replace('High trajectory reconstruction error', 'Quỹ đạo di chuyển có sai số tái tạo cao')
    .replace(/^Long dwell in ([^:]+):/, 'Ở $1 quá lâu:')
    .replace(/^Impossible\/unlikely transition:/, 'Chuyển phòng không phù hợp sơ đồ nhà:')
    .replace(/^Unusual nighttime dwell in ([^:]+):/, 'Lưu trú ban đêm bất thường tại $1:')
    .replace(/^Unusual nighttime movement:/, 'Di chuyển ban đêm bất thường:')
    .replace(/^No detected movement for/, 'Không phát hiện vận động trong')
    .replace('Possible impact followed by low motion; caregiver review required',
      'Ghi nhận va chạm rồi ít vận động; cần người chăm sóc kiểm tra');
}

/* ------------------------------------------------------------ chuyển động --- */
/* Nguyên tắc: chỉ đánh dấu "vừa đổi" cho đúng phần tử vừa đổi, chạy một lần,
   dùng opacity/transform. Không có vòng lặp vô hạn trên dữ liệu. */

export function flash(element) {
  if (!element || REDUCED_MOTION) return;
  element.classList.remove('is-updated');
  void element.offsetWidth;           // ép trình duyệt chạy lại animation
  element.classList.add('is-updated');
}

export function pulse(element) {
  if (!element || REDUCED_MOTION) return;
  element.classList.remove('is-alerting');
  void element.offsetWidth;
  element.classList.add('is-alerting');
}

/**
 * Ghi văn bản, chỉ chạm DOM khi giá trị thật sự đổi.
 *
 * `animate` mặc định là false — cố ý. Phần lớn ô trên dashboard (thời gian lưu
 * trú, độ tin cậy, điểm bất thường, giờ cập nhật) đổi theo từng mẫu; nhấp nháy
 * chúng mỗi 2 giây là làm dữ liệu người dùng đang đọc rung lên vô ích.
 * Chỉ bật `animate` cho những thay đổi có ý nghĩa: vị trí, trạng thái an toàn,
 * mức hoạt động, chỉ số thực nghiệm.
 */
export function setField(element, value, animate = false) {
  if (!element) return false;
  const next = value == null ? '—' : String(value);
  if (element.textContent === next) return false;
  element.textContent = next;
  if (animate) flash(element);
  return true;
}

/** Thanh tiến độ dùng transform:scaleX (không gây layout như width). */
export function setBar(element, ratio) {
  if (!element) return;
  const clamped = Math.max(0, Math.min(1, Number.isFinite(ratio) ? ratio : 0));
  element.style.transform = `scaleX(${clamped})`;
}

document.addEventListener('animationend', event => {
  if (event.animationName === 'fieldUpdate') event.target.classList.remove('is-updated');
  if (event.animationName === 'attentionPulse') event.target.classList.remove('is-alerting');
});

/* ----------------------------------------------------------------- API ------ */
/** Lỗi HTTP có kèm mã trạng thái và payload để tầng trên xử lý. */
export class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

export async function api(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json';

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
      signal: options.signal || controller.signal,
      credentials: 'same-origin',
      cache: 'no-store'          // tránh dữ liệu cũ từ cache trình duyệt
    });
  } catch (error) {
    if (error.name === 'AbortError') throw new ApiError('Máy chủ phản hồi quá lâu', 0, {});
    throw error;
  } finally {
    clearTimeout(timeout);
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new ApiError(data.error || `${response.status} ${response.statusText}`, response.status, data);
  }
  return data;
}

/** Không bao giờ để một promise bị treo thành lỗi "unhandled rejection". */
export function ignore(promise) {
  Promise.resolve(promise).catch(error => console.error(error));
}

/* -------------------------------------------------------------- nút bấm ----- */
/**
 * Nhãn nhàn rỗi được lưu lại mỗi lần đặt nhãn mới, tránh lỗi cũ: nút quay về
 * nhãn cũ sau khi renderCalibration/renderTrainingJob đổi nhãn.
 */
export function setButtonLabel(button, text) {
  if (!button) return;
  button.textContent = text;
  button.dataset.idleLabel = text;
}

export function setButtonBusy(button, busy, busyText = 'Đang xử lý…') {
  if (!button) return;
  if (busy) {
    if (!button.dataset.idleLabel) button.dataset.idleLabel = button.textContent;
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    button.textContent = busyText;
  } else {
    button.removeAttribute('aria-busy');
    button.disabled = false;
    if (button.dataset.idleLabel) button.textContent = button.dataset.idleLabel;
  }
}
