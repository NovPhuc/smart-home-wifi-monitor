/* =============================================================================
 * An Tâm Home — giao diện hợp nhất
 * -----------------------------------------------------------------------------
 * File này thay thế app.js (bản cũ) + app-v2.js (trang demo) + app-v3.js
 * (dashboard tài khoản). Nó giữ ưu điểm của cả hai bản:
 *   • của app-v2.js: dịch đầy đủ lý do cảnh báo, đổi nhãn phòng sang tiếng Việt,
 *     trạng thái badge cảm biến, bấm ô phòng để mô phỏng (trang demo).
 *   • của app-v3.js: đăng nhập, nhiều căn nhà, chia sẻ, thiết lập, hiệu chuẩn,
 *     huấn luyện, chống XSS, chỉ vẽ lại DOM khi dữ liệu thật sự đổi.
 * và sửa các lỗi tồn tại (xem docs/07_kiem_tra_loi_ui_va_toi_uu.md).
 *
 * Một file chạy cho cả server/templates/dashboard.html và index.html:
 * mọi phần tử không tồn tại sẽ được bỏ qua thay vì ném lỗi.
 * ========================================================================== */
'use strict';

/* ---------------------------------------------------------------- hằng số -- */
const POLL_MS = 2000;            // nhịp hỏi /api/status khi tab đang mở
const REQUEST_TIMEOUT_MS = 8000; // quá hạn thì hủy để không xếp hàng request
const STALE_AFTER_S = 15;        // dữ liệu cũ hơn mức này coi như mất kết nối
const DEMO_STEP_MS = 900;
const HISTORY_LIMIT = 12;
const ALERT_LIMIT = 6;

const DEMO_ROOM_NAMES = {
  Bedroom: 'Phòng ngủ', Corridor: 'Hành lang', Bathroom: 'Phòng tắm',
  LivingRoom: 'Phòng khách', Kitchen: 'Nhà bếp'
};

const ACTIVITY = {
  CALIBRATING: ['Đang hiệu chuẩn', 'Cần vài mẫu tín hiệu đầu tiên', 'CAL'],
  STILL: ['Đang nghỉ ngơi', 'Không ghi nhận biến động đáng kể', 'YÊN'],
  LIGHT_ACTIVITY: ['Hoạt động nhẹ', 'Tín hiệu thay đổi nhẹ trong phòng', 'NHẸ'],
  MOVING: ['Đang di chuyển', 'Phát hiện biến động tín hiệu Wi-Fi', 'ĐI'],
  ROOM_CHANGE: ['Vừa chuyển phòng', 'Đã xác nhận thay đổi vị trí', 'ĐỔI']
};

const SAFETY_COPY = {
  NORMAL: ['AN TOÀN', 'OK', 'Sinh hoạt bình thường'],
  WARNING: ['CẦN CHÚ Ý', '!', 'Có dấu hiệu cần kiểm tra'],
  CRITICAL: ['KHẨN CẤP', '!!', 'Phát hiện bất thường nghiêm trọng'],
  COLLECTING: ['ĐANG GOM MẪU', 'OK', 'Hệ thống sẵn sàng'],
  NO_DATA: ['CHƯA CÓ DỮ LIỆU', 'OK', 'Hệ thống sẵn sàng']
};

const SIGNAL_COPY = { GOOD: 'Tín hiệu tốt', FAIR: 'Tín hiệu vừa', WEAK: 'Tín hiệu yếu' };
const SENSOR_COPY = {
  MOVING: 'Đang di chuyển', STILL: 'Đang đứng yên',
  IMPACT_RECORDED: 'Ghi nhận va chạm', NO_DATA: 'Chưa có dữ liệu'
};

/* ---------------------------------------------------------- trạng thái ------ */
const state = {
  authenticated: false,
  me: null,
  rooms: [],
  devices: [],
  calibration: null,
  demoMode: false,
  lastRoom: null,
  lastSafety: null
};

let demoTimer = null;
let pollTimer = null;
let trainingTimer = null;
let refreshInFlight = false;
let refreshPending = false;
let sensorActive = false;
let lastSensorSentAt = 0;
const lastRenderKey = { status: '', history: '', alerts: '' };

/* ------------------------------------------------------------ tiện ích ------ */
const $ = id => document.getElementById(id);

/** Gắn sự kiện an toàn: bỏ qua nếu phần tử không có trên trang hiện tại. */
function on(id, type, handler) {
  const element = typeof id === 'string' ? $(id) : id;
  if (element) element.addEventListener(type, handler);
  return element;
}

const REDUCED_MOTION = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;

/** localStorage có thể bị chặn (Safari riêng tư) — không được làm chết app. */
const storage = {
  get(key) { try { return localStorage.getItem(key); } catch { return null; } },
  set(key, value) { try { localStorage.setItem(key, value); } catch { /* bỏ qua */ } }
};

/** crypto.randomUUID chỉ có trên HTTPS/localhost; LAN HTTP phải có đường lui. */
function makeDeviceId(prefix) {
  const random = globalThis.crypto?.randomUUID?.()
    || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
  return `${prefix}-${random}`;
}

const deviceId = storage.get('an-tam-device-id') || makeDeviceId('phone');
storage.set('an-tam-device-id', deviceId);

const escapeHTML = value => String(value ?? '').replace(/[&<>'"]/g, c => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]
));

const roomLabel = name => DEMO_ROOM_NAMES[name] || name || 'Chưa xác định';

const fmtTime = ts => ts
  ? new Date(ts * 1000).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
  : '—';

function fmtDuration(minutes) {
  if (minutes == null) return '—';
  if (minutes < 1) return `${Math.round(minutes * 60)} giây`;
  if (minutes < 60) return `${minutes.toFixed(1)} phút`;
  return `${Math.floor(minutes / 60)}g ${Math.round(minutes % 60)}p`;
}

/** Bản dịch lý do cảnh báo — giữ đủ mẫu của app-v2.js (app-v3.js đã làm rơi 3 mẫu). */
function translateReason(reason) {
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

function flash(element) {
  if (!element || REDUCED_MOTION) return;
  element.classList.remove('is-updated');
  void element.offsetWidth;           // ép trình duyệt chạy lại animation
  element.classList.add('is-updated');
}

function pulse(element) {
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
function setField(element, value, animate = false) {
  if (!element) return false;
  const next = value == null ? '—' : String(value);
  if (element.textContent === next) return false;
  element.textContent = next;
  if (animate) flash(element);
  return true;
}

/** Thanh tiến độ dùng transform:scaleX (không gây layout như width). */
function setBar(element, ratio) {
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
class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

async function api(url, options = {}) {
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
function ignore(promise) {
  Promise.resolve(promise).catch(error => console.error(error));
}

/* -------------------------------------------------------------- nút bấm ----- */
/**
 * Nhãn nhàn rỗi được lưu lại mỗi lần đặt nhãn mới, tránh lỗi cũ: nút quay về
 * nhãn cũ sau khi renderCalibration/renderTrainingJob đổi nhãn.
 */
function setButtonLabel(button, text) {
  if (!button) return;
  button.textContent = text;
  button.dataset.idleLabel = text;
}

function setButtonBusy(button, busy, busyText = 'Đang xử lý…') {
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

/* ============================== XÁC THỰC ================================== */
function showAuth(register = false) {
  state.authenticated = false;
  if ($('authView')) $('authView').hidden = false;
  if ($('appShell')) $('appShell').hidden = true;
  selectAuthTab(register ? 'register' : 'login');
  stopPolling();
  stopTrainingPolling();
  stopDemo();
}

function selectAuthTab(name) {
  const register = name === 'register';
  if ($('loginTab')) $('loginTab').setAttribute('aria-selected', String(!register));
  if ($('registerTab')) $('registerTab').setAttribute('aria-selected', String(register));
  if ($('loginForm')) $('loginForm').hidden = register;
  if ($('registerForm')) $('registerForm').hidden = !register;
  if ($('authError')) $('authError').hidden = true;
}

function clearFieldErrors(form) {
  if (!form) return;
  form.querySelectorAll('.field-error').forEach(element => { element.textContent = ''; });
  form.querySelectorAll('[aria-invalid="true"]').forEach(element => element.removeAttribute('aria-invalid'));
}

function showAuthErrors(form, message, fields = {}) {
  clearFieldErrors(form);
  const summary = $('authError');
  if (summary) {
    summary.textContent = message;
    summary.hidden = false;
    summary.focus();
  }
  const idMap = {
    display_name: 'displayName',
    email: form?.id === 'loginForm' ? 'loginEmail' : 'registerEmail',
    password: form?.id === 'loginForm' ? 'loginPassword' : 'registerPassword',
    home_name: 'firstHomeName'
  };
  Object.entries(fields).forEach(([field, text]) => {
    const input = $(idMap[field]);
    const target = $(`${idMap[field]}Error`);
    if (input) input.setAttribute('aria-invalid', 'true');
    if (target) target.textContent = text;
  });
}

async function submitAuth(form, endpoint) {
  clearFieldErrors(form);
  if ($('authError')) $('authError').hidden = true;
  if (!form.reportValidity()) return;
  const button = form.querySelector('button[type="submit"]');
  setButtonBusy(button, true);
  try {
    await api(endpoint, { method: 'POST', body: JSON.stringify(Object.fromEntries(new FormData(form).entries())) });
    form.reset();
    await loadApplication();
  } catch (error) {
    const wrongCredentials = error.data?.error === 'INVALID_CREDENTIALS';
    showAuthErrors(form, wrongCredentials ? 'Email hoặc mật khẩu không đúng' : 'Vui lòng kiểm tra thông tin.',
      error.data?.fields || {});
  } finally {
    setButtonBusy(button, false);
  }
}

/* ============================== KHỞI ĐỘNG ================================= */
async function loadApplication() {
  try {
    state.me = await api('/api/auth/me');
  } catch (error) {
    if (error.status === 401) { showAuth(false); return; }
    throw error;
  }
  state.authenticated = true;
  if ($('authView')) $('authView').hidden = true;
  if ($('appShell')) $('appShell').hidden = false;
  if ($('accountName')) $('accountName').textContent = state.me.user.display_name;
  if ($('accountEmail')) $('accountEmail').textContent = state.me.user.email;
  renderHomes();
  await loadHome();
  startPolling();
}

function startPolling() {
  stopPolling();
  pollTimer = setInterval(() => ignore(refreshDashboard()), POLL_MS);
}

function stopPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = null;
}

function stopTrainingPolling() {
  if (trainingTimer) clearInterval(trainingTimer);
  trainingTimer = null;
}

function renderHomes() {
  const homes = state.me?.homes || [];
  const select = $('homeSelect');
  if (select) {
    select.innerHTML = homes.map(home => {
      const selected = state.me?.active_home?.id === home.id ? ' selected' : '';
      const shared = home.role === 'member' ? ' (được chia sẻ)' : '';
      return `<option value="${home.id}"${selected}>${escapeHTML(home.name)}${shared}</option>`;
    }).join('');
  }
  if ($('homeTitle')) $('homeTitle').textContent = state.me?.active_home?.name || 'An Tâm Home';
  document.body.classList.toggle('member-mode', state.me?.active_home?.role === 'member');
}

async function loadHome() {
  const [rooms, devices, calibration] = await Promise.all([
    api('/api/rooms'), api('/api/devices'), api('/api/calibration')
  ]);
  state.rooms = rooms;
  state.devices = devices;
  state.calibration = calibration;
  state.demoMode = false;
  state.lastRoom = null;
  state.lastSafety = null;
  lastRenderKey.status = lastRenderKey.history = lastRenderKey.alerts = '';
  document.body.classList.remove('demo-mode');
  renderRooms();
  renderDevices();
  renderCalibration(calibration);
  await Promise.all([
    refreshDashboard(),
    api('/api/metrics').then(renderMetrics).catch(() => renderMetrics({}))
  ]);
  ignore(checkTrainingStatus());
}

/* ============================== THIẾT LẬP ================================= */
function renderRooms() {
  const list = $('roomList');
  if (list) {
    list.innerHTML = state.rooms.map(room => `
      <div class="entity-row">
        <div><strong>${escapeHTML(room.name)}</strong>
          <small>Cảnh báo lưu trú sau ${room.max_dwell_minutes} phút</small></div>
        <button type="button" data-delete-room="${room.id}"
          aria-label="Xóa phòng ${escapeHTML(room.name)}">Xóa</button>
      </div>`).join('') || '<div class="empty-state">Chưa có phòng. Hãy thêm ít nhất hai phòng.</div>';
    list.querySelectorAll('[data-delete-room]').forEach(button => {
      button.addEventListener('click', () => ignore(deleteRoom(Number(button.dataset.deleteRoom))));
    });
  }
  renderRoomGrid();
}

/**
 * Lưới phòng. Khi chạy demo, model mẫu trả về 5 phòng tổng hợp (Bedroom…),
 * không phải tên phòng của căn nhà — nên lưới phải đổi theo, nếu không sẽ
 * không ô nào sáng (lỗi có ở bản app-v3.js).
 */
function roomGridEntries() {
  if (state.demoMode) {
    return Object.entries(DEMO_ROOM_NAMES).map(([key, label]) => ({ key, label }));
  }
  return state.rooms.map(room => ({ key: room.name, label: room.name }));
}

function renderRoomGrid() {
  const grid = $('roomGrid');
  if (!grid) return;                       // index.html dùng .floorplan tĩnh
  const entries = roomGridEntries();
  grid.innerHTML = entries.map(entry => `
    <div class="room-tile" role="listitem" data-room="${escapeHTML(entry.key)}">
      <span>${escapeHTML(entry.label)}</span>
      <small>Đang chờ định vị</small>
    </div>`).join('') || '<div class="empty-state">Chưa thiết lập phòng.</div>';
  applyActiveRoom(state.lastRoom);
}

function applyActiveRoom(room) {
  const scope = $('roomGrid') || document.querySelector('.floorplan');
  if (!scope) return;
  scope.querySelectorAll('.room-tile').forEach(tile => {
    const active = Boolean(room) && tile.dataset.room === room;
    const wasActive = tile.classList.contains('active');
    tile.classList.toggle('active', active);
    tile.setAttribute('aria-current', active ? 'true' : 'false');
    if (active && !wasActive && !REDUCED_MOTION) {
      tile.classList.remove('is-entering');
      void tile.offsetWidth;
      tile.classList.add('is-entering');
    }
    const hint = tile.querySelector('small');
    if (hint) hint.textContent = active ? 'Đang ở đây' : (state.demoMode ? 'Phòng mẫu' : 'Không có người');
  });
}

function renderDevices() {
  const list = $('deviceList');
  if (!list) return;
  list.innerHTML = state.devices.map(device => `
    <div class="entity-row">
      <div><strong>${escapeHTML(device.name)}</strong>
        <small>${escapeHTML(device.platform)} • mã …${escapeHTML(device.token_hint)}${
          device.last_seen_at ? ` • dùng lúc ${fmtTime(device.last_seen_at)}` : ''}</small></div>
      <button type="button" data-revoke-device="${device.id}"
        aria-label="Thu hồi thiết bị ${escapeHTML(device.name)}">Thu hồi</button>
    </div>`).join('') || '<div class="empty-state">Chưa có điện thoại được ghép.</div>';
  list.querySelectorAll('[data-revoke-device]').forEach(button => {
    button.addEventListener('click', () => ignore(revokeDevice(Number(button.dataset.revokeDevice))));
  });
}

/**
 * Lưới tiến độ thu dữ liệu.
 *
 * Chỉ dựng lại DOM khi danh sách phòng đổi; những nhịp sau chỉ cập nhật số
 * liệu. Bản cũ dựng lại innerHTML mỗi nhịp nên thanh tiến độ không bao giờ
 * chạy được transition — nó nhảy thẳng tới giá trị mới.
 */
function renderCalibrationRooms(rooms) {
  const grid = $('calibrationRooms');
  if (!grid) return;
  const signature = rooms.map(room => room.name).join('|');
  if (grid.dataset.signature !== signature) {
    grid.dataset.signature = signature;
    grid.innerHTML = rooms.map(room => `
      <div class="calibration-room">
        <header><strong>${escapeHTML(room.name)}</strong><span data-state></span></header>
        <div class="progress-track" role="progressbar"
             aria-label="Tiến độ phòng ${escapeHTML(room.name)}">
          <i data-fill></i></div>
        <small data-meta></small>
      </div>`).join('') || '<div class="empty-state">Thêm phòng để bắt đầu thu dữ liệu.</div>';
  }
  rooms.forEach((room, index) => {
    const card = grid.children[index];
    if (!card || typeof card.querySelector !== 'function') return;
    card.classList.toggle('ready', Boolean(room.ready));
    setField(card.querySelector('[data-state]'), room.ready ? 'Đạt' : 'Đang thu', true);
    const track = card.querySelector('.progress-track');
    if (track) {
      track.setAttribute('aria-valuemin', '0');
      track.setAttribute('aria-valuemax', String(room.target_samples || 1));
      track.setAttribute('aria-valuenow', String(room.samples ?? 0));
    }
    setBar(card.querySelector('[data-fill]'), (room.samples || 0) / (room.target_samples || 1));
    setField(card.querySelector('[data-meta]'),
      `${room.samples}/${room.target_samples} mẫu • ${room.orientations}/${room.required_orientations} hướng • ${room.sessions}/${room.required_sessions} phiên`);
  });
}

function renderCalibration(calibration) {
  if (!calibration) return;
  state.calibration = calibration;

  const steps = [
    ['stepRooms', state.rooms.length >= 2],
    ['stepDevice', state.devices.length > 0],
    ['stepCollect', Boolean(calibration.data_ready)],
    ['stepTrain', Boolean(calibration.localization_ready)]
  ];
  steps.forEach(([id, done]) => {
    const element = $(id);
    if (!element) return;
    const wasComplete = element.classList.contains('complete');
    element.classList.toggle('complete', done);
    if (done && !wasComplete) pulse(element);   // chỉ nhấp nháy lúc vừa hoàn thành
  });

  renderCalibrationRooms(calibration.rooms || []);

  const ready = Boolean(calibration.localization_ready);
  document.body.classList.toggle('calibration-required', !ready && !state.demoMode);

  const status = $('setupStatus');
  if (status) {
    status.textContent = ready ? 'SẴN SÀNG'
      : calibration.model_status === 'TRAINING' ? 'ĐANG HUẤN LUYỆN' : 'CHƯA SẴN SÀNG';
    status.className = `badge ${ready ? 'normal' : calibration.model_status === 'TRAINING' ? 'warning' : 'neutral'}`;
  }

  const trainable = Boolean(calibration.data_ready) && calibration.model_status !== 'TRAINING';
  const trainButton = $('trainButton');
  if (trainButton) {
    trainButton.disabled = !trainable;
    setButtonLabel(trainButton, calibration.model_status === 'READY'
      ? 'Huấn luyện lại model' : 'Huấn luyện model căn nhà');
  }

  setField($('trainingTitle'), ready ? 'Model căn nhà đã sẵn sàng'
    : calibration.data_ready ? 'Đã đủ dữ liệu để huấn luyện' : 'Chưa đủ dữ liệu huấn luyện');
  setField($('trainingMeta'), ready ? 'Định vị thời gian thực đã được mở.'
    : calibration.data_ready ? 'Bấm huấn luyện và giữ máy chủ hoạt động.'
      : 'Mỗi phòng cần đủ mẫu, hướng cầm và 3 phiên.');
}

async function deleteRoom(id) {
  if (!confirm('Xóa phòng sẽ xóa toàn bộ scan đã thu của phòng này. Tiếp tục?')) return;
  await api(`/api/rooms/${id}`, { method: 'DELETE' });
  await loadHome();
}

async function revokeDevice(id) {
  if (!confirm('Thu hồi mã ghép nối của thiết bị này?')) return;
  await api(`/api/devices/${id}`, { method: 'DELETE' });
  state.devices = await api('/api/devices');
  renderDevices();
  renderCalibration(state.calibration);
}

/* ============================== GIÁM SÁT ================================== */
function setConnection(ok, timestamp) {
  const stale = Boolean(timestamp) && Date.now() / 1000 - timestamp > STALE_AFTER_S;
  const dot = $('statusDot');
  if (dot) dot.className = ok && !stale ? 'live' : 'error';
  setField($('statusText'), !ok ? 'Mất kết nối' : stale ? 'Dữ liệu đã cũ' : 'Hệ thống trực tuyến');
}

function renderStatus(status) {
  const room = status.room;
  if (room !== state.lastRoom) {
    state.lastRoom = room;
    applyActiveRoom(room);
  }
  // Ngay sau khi khởi động lại máy chủ, vài mẫu demo đầu tiên chưa đủ để model
  // mẫu chốt phòng (đo thật 2026-10-27: phải chờ tới mẫu thứ 2-3 mới ra phòng).
  // Nói rõ đang khởi động thay vì để "Chưa có dữ liệu" khô khan.
  const warmingUp = !room && status.demo;
  setField($('room'), room ? roomLabel(room) : warmingUp ? 'Đang lấy mẫu…' : 'Chưa có dữ liệu', true);
  setField($('roomMeta'), room
    ? `${status.demo ? 'Demo mẫu' : 'Model căn nhà'} • định vị mức phòng`
    : warmingUp ? 'Model mẫu đang khởi động — chờ thêm vài mẫu tín hiệu…'
      : 'Đang chờ fingerprint Wi-Fi…');
  setField($('confidence'), status.confidence != null ? `TIN CẬY ${(status.confidence * 100).toFixed(0)}%` : '—');
  setField($('dwell'), fmtDuration(status.dwell_minutes));
  setField($('score'), status.anomaly_score != null ? status.anomaly_score.toFixed(3) : '—');

  const ratio = status.anomaly_score != null && status.anomaly_threshold
    ? status.anomaly_score / status.anomaly_threshold : 0;
  setBar($('meterFill'), ratio);

  const activity = status.activity || {};
  const copy = ACTIVITY[activity.state] || ACTIVITY.CALIBRATING;
  setField($('activityState'), copy[0], true);
  setField($('activityMeta'), copy[1]);
  setField($('activityIcon'), copy[2], true);
  setField($('transitions'), activity.transitions_last_hour ?? '—');

  const safety = (status.status || 'NO_DATA').toUpperCase();
  const [badge, icon, title] = SAFETY_COPY[safety] || [safety, 'OK', 'Hệ thống sẵn sàng'];
  const card = $('safetyCard');
  if (card) card.className = `card safety-card ${safety.toLowerCase()}`;
  if ($('systemBadge')) $('systemBadge').className = `badge ${safety === 'NO_DATA' ? 'neutral' : safety.toLowerCase()}`;
  setField($('systemBadge'), badge, true);
  setField($('safetyIcon'), icon, true);
  setField($('safetyTitle'), title, true);
  setField($('safetyDescription'), translateReason((status.reasons || [])[0]) || 'Không có cảnh báo cần xử lý.');

  // Chỉ nhấp nháy khi trạng thái an toàn leo thang — không lặp vô hạn.
  if (safety !== state.lastSafety) {
    const escalated = state.lastSafety !== null && (safety === 'WARNING' || safety === 'CRITICAL');
    state.lastSafety = safety;
    if (escalated) pulse(card);
  }

  const probabilities = status.smoothed_probabilities || {};
  const probabilityBox = $('probabilities');
  if (probabilityBox) {
    probabilityBox.innerHTML = Object.entries(probabilities).map(([name, value]) => `
      <div class="probability">
        <span>${escapeHTML(roomLabel(name))} ${(value * 100).toFixed(0)}%</span>
        <div><i style="transform:scaleX(${Math.max(0, Math.min(1, value))})"></i></div>
      </div>`).join('');
  }

  const signal = status.signal || {};
  const dot = $('signalDot');
  if (dot) dot.className = (signal.quality || '').toLowerCase();
  setField($('signalText'), signal.quality
    ? `${signal.visible_access_points} AP • ${SIGNAL_COPY[signal.quality] || signal.quality}`
    : 'Chưa có tín hiệu');
  setField($('lastUpdate'), fmtTime(status.timestamp));

  if (status.calibration) renderCalibration(status.calibration);
  if (status.mobile_sensor) renderMobileSensor(status.mobile_sensor);
}

function compactHistory(history) {
  const result = [];
  for (const item of history) {
    const last = result[result.length - 1];
    if (!last || last.room !== item.room) result.push(item);
    else result[result.length - 1] = item;
  }
  return result.slice(-HISTORY_LIMIT).reverse();
}

function renderHistory(history) {
  const items = compactHistory(history);
  setField($('historyCount'), `${items.length} sự kiện`);
  const box = $('history');
  if (!box) return;
  box.innerHTML = items.map((item, index) => `
    <div class="timeline-item ${index < items.length - 1 ? 'transition' : ''}${index === 0 ? ' is-new' : ''}">
      <time>${fmtTime(item.timestamp)}</time>
      <strong>${escapeHTML(roomLabel(item.room))}</strong>
      <span>${item.activity?.state === 'ROOM_CHANGE' ? 'Chuyển phòng' : fmtDuration(item.dwell_minutes)}</span>
    </div>`).join('') || '<div class="empty-state">Dữ liệu hoạt động sẽ xuất hiện tại đây.</div>';
}

function renderAlerts(alerts) {
  setField($('alertCount'), alerts.length);
  const box = $('alertsList');
  if (!box) return;
  // Chỉ mục mới nhất được đánh dấu is-new: cảnh báo ập tới thì chỉ nó chuyển
  // động, danh sách phía dưới đứng yên.
  box.innerHTML = alerts.slice(-ALERT_LIMIT).reverse().map((item, index) => `
    <div class="alert ${(item.status || '').toLowerCase()}${index === 0 ? ' is-new' : ''}">
      <strong>${escapeHTML(roomLabel(item.room) || 'Cảm biến')} • ${escapeHTML(item.status)}</strong>
      <span>${escapeHTML((item.reasons || []).map(translateReason).join(' · '))}</span>
    </div>`).join('') || '<div class="empty-state">Chưa có cảnh báo.</div>';
}

function renderMetrics(metrics = {}) {
  const room = metrics.room_model || {};
  const anomaly = metrics.anomaly_model || {};
  setField($('metricAccuracy'), room.accuracy != null ? `${(room.accuracy * 100).toFixed(2)}%` : '—', true);
  setField($('metricF1'), room.macro_f1 != null ? `${(room.macro_f1 * 100).toFixed(2)}%` : '—', true);
  setField($('metricRecall'), anomaly.recall != null ? `${(anomaly.recall * 100).toFixed(2)}%` : 'Chưa train', true);
  setField($('metricLatency'), room.mean_inference_ms != null ? `${room.mean_inference_ms.toFixed(3)} ms` : '—', true);

  const comparisons = [
    ['RoomNet-Lite', room.accuracy],
    ...Object.entries(metrics.baselines || {}).map(([name, values]) => [name, values?.accuracy])
  ].filter(([, value]) => value != null);

  const box = $('baselineComparison');
  if (box) {
    box.innerHTML = comparisons.map(([name, value]) => `
      <div><span>${escapeHTML(name)}</span>
        <div><i style="transform:scaleX(${Math.max(0, Math.min(1, value))})"></i></div>
        <strong>${(value * 100).toFixed(2)}%</strong></div>`).join('');
  }
}

/**
 * Một hàm vẽ không được phép làm chết cả nhịp cập nhật.
 *
 * Nếu render ném lỗi mà lỗi đó thoát ra `refreshDashboard`, phần `catch` sẽ
 * hiểu nhầm là mất mạng và ghi "Mất kết nối" dù máy chủ vẫn tốt.
 */
function safeRender(name, render) {
  try {
    render();
    return true;
  } catch (error) {
    console.error(`[An Tâm] lỗi khi vẽ ${name}:`, error);
    return false;
  }
}

/**
 * Một nhịp hỏi dữ liệu.
 *
 * Bản cũ `return` khi đang có request bay — nhịp đó bị BỎ chứ không hẹn lại,
 * nên dữ liệu mới có thể không bao giờ được vẽ (demo 900ms/bước trong khi
 * poll 2000ms rất dễ rơi vào cảnh này). Giờ chỉ đánh dấu `refreshPending`.
 *
 * Khoá cache cũng được ghi SAU khi vẽ xong: nếu vẽ lỗi thì nhịp sau còn thử
 * lại, thay vì tưởng đã vẽ rồi và bỏ qua vĩnh viễn.
 */
async function refreshDashboard() {
  if ($('appShell') && !state.authenticated) return;
  if (document.hidden) return;
  if (refreshInFlight) { refreshPending = true; return; }
  refreshInFlight = true;
  try {
    const [status, history, alerts] = await Promise.all([
      api('/api/status'), api('/api/history'), api('/api/alerts')
    ]);
    setConnection(true, status.timestamp);

    const statusKey = JSON.stringify([
      status.room, status.status, status.confidence, status.dwell_minutes, status.anomaly_score,
      status.timestamp, status.activity, status.signal, status.smoothed_probabilities,
      status.calibration, status.mobile_sensor
    ]);
    if (statusKey !== lastRenderKey.status && safeRender('trạng thái', () => renderStatus(status))) {
      lastRenderKey.status = statusKey;
    }

    const historyKey = JSON.stringify(history.map(item => [item.timestamp, item.room, item.dwell_minutes, item.activity?.state]));
    if (historyKey !== lastRenderKey.history && safeRender('dòng thời gian', () => renderHistory(history))) {
      lastRenderKey.history = historyKey;
    }

    const alertsKey = JSON.stringify(alerts.map(item => [item.id, item.status]));
    if (alertsKey !== lastRenderKey.alerts && safeRender('cảnh báo', () => renderAlerts(alerts))) {
      lastRenderKey.alerts = alertsKey;
    }
  } catch (error) {
    if (error.status === 401 && $('appShell')) showAuth();
    else setConnection(false);
  } finally {
    refreshInFlight = false;
    if (refreshPending) {
      refreshPending = false;
      ignore(refreshDashboard());
    }
  }
}

/* ============================== DEMO ===================================== */
async function demoStep(room) {
  await api('/api/demo/scan', { method: 'POST', body: JSON.stringify(room ? { room } : {}) });
  await refreshDashboard();
}

function stopDemo() {
  if (demoTimer) clearInterval(demoTimer);
  demoTimer = null;
  if (!state.demoMode) return;
  state.demoMode = false;
  document.body.classList.remove('demo-mode');
  const toggle = $('demoToggle');
  if (toggle) {
    toggle.classList.remove('running');
    toggle.setAttribute('aria-pressed', 'false');
    setButtonLabel(toggle, 'Chạy demo');
  }
  if ($('roomGrid')) renderRoomGrid();
  if (state.calibration) renderCalibration(state.calibration);
}

function startDemo() {
  state.demoMode = true;
  document.body.classList.add('demo-mode');
  document.body.classList.remove('calibration-required');
  const toggle = $('demoToggle');
  if (toggle) {
    toggle.classList.add('running');
    toggle.setAttribute('aria-pressed', 'true');
    setButtonLabel(toggle, 'Dừng demo');
  }
  setField($('demoStatus'), 'Đang phát fingerprint mẫu…');
  if ($('roomGrid')) renderRoomGrid();
  const fail = error => {
    stopDemo();
    setField($('demoStatus'), `Không chạy được demo: ${error.message}`);
  };
  ignore(demoStep().catch(fail));
  demoTimer = setInterval(() => ignore(demoStep().catch(fail)), DEMO_STEP_MS);
}

function toggleDemo() {
  if (demoTimer) {
    stopDemo();
    setField($('demoStatus'), 'Đã tạm dừng demo.');
  } else {
    startDemo();
  }
}

/** Trang demo cũ: bấm một ô phòng để gửi 6 fingerprint của đúng phòng đó. */
async function selectDemoRoom(room) {
  stopDemo();
  const tiles = document.querySelectorAll('.room-tile');
  tiles.forEach(tile => { tile.disabled = true; });
  setField($('demoStatus'), `Đang mô phỏng ${roomLabel(room)}…`);
  try {
    for (let index = 0; index < 6; index += 1) await demoStep(room);
    setField($('demoStatus'), `Đã gửi fingerprint của ${roomLabel(room)}.`);
  } catch (error) {
    setField($('demoStatus'), `Không chạy được demo: ${error.message}`);
  } finally {
    tiles.forEach(tile => { tile.disabled = false; });
  }
}

/* ============================== CẢM BIẾN ================================= */
function renderMobileSensor(sensor) {
  if (!sensor) return;
  setField($('sensorBadge'), SENSOR_COPY[sensor.state] || sensor.state);
  const badge = $('sensorBadge');
  if (badge) {
    badge.className = `badge ${sensor.possible_impact ? 'warning' : sensor.state === 'NO_DATA' ? 'neutral' : 'normal'}`;
  }
  if (sensor.last_seen_at) {
    setField($('sensorMeta'),
      `${sensor.samples_received} mẫu • ${Number(sensor.motion_magnitude).toFixed(2)} m/s² • ${fmtTime(sensor.last_seen_at)}`);
  }
}

async function sendMotion(acceleration) {
  try {
    renderMobileSensor(await api('/api/sensor', {
      method: 'POST',
      body: JSON.stringify({ device_id: deviceId, timestamp: Date.now() / 1000, acceleration })
    }));
  } catch (error) {
    setField($('sensorMeta'), `Không gửi được dữ liệu: ${error.message}`);
  }
}

/** Cảnh báo "không có gia tốc tuyến tính" chỉ nói một lần cho mỗi lần bật cảm biến. */
let sensorAccelerationWarned = false;

function onDeviceMotion(event) {
  const acceleration = event.acceleration;
  if (!acceleration || acceleration.x == null || acceleration.y == null || acceleration.z == null) {
    // app-v2.js có báo việc này, app-v3.js bỏ im lặng. Ghi lại ở MỖI sự kiện sẽ đè
    // liên tục lên thông tin hữu ích trong #sensorMeta, nên chỉ nói một lần.
    if (!sensorAccelerationWarned) {
      sensorAccelerationWarned = true;
      setField($('sensorMeta'), 'Thiết bị không cung cấp gia tốc tuyến tính.');
    }
    return;
  }
  const magnitude = Math.hypot(acceleration.x, acceleration.y, acceleration.z);
  const now = performance.now();
  if (magnitude < 18 && now - lastSensorSentAt < 500) return;
  lastSensorSentAt = now;
  ignore(sendMotion({ x: acceleration.x, y: acceleration.y, z: acceleration.z }));
}

async function toggleSensor() {
  const toggle = $('sensorToggle');
  if (sensorActive) {
    window.removeEventListener('devicemotion', onDeviceMotion);
    sensorActive = false;
    if (toggle) {
      setButtonLabel(toggle, 'Bật cảm biến iPhone');
      toggle.setAttribute('aria-pressed', 'false');
    }
    // Bản app-v3.js quên đặt lại badge — đây là chỗ sửa.
    setField($('sensorBadge'), 'TẮT');
    const badge = $('sensorBadge');
    if (badge) badge.className = 'badge neutral';
    setField($('sensorMeta'), 'Đã dừng gửi dữ liệu cảm biến.');
    return;
  }
  if (!window.isSecureContext) {
    setField($('sensorMeta'), 'Cần HTTPS để Safari cấp quyền cảm biến.');
    return;
  }
  if (typeof DeviceMotionEvent === 'undefined') {
    setField($('sensorMeta'), 'Thiết bị không hỗ trợ DeviceMotion.');
    return;
  }
  try {
    if (typeof DeviceMotionEvent.requestPermission === 'function'
      && await DeviceMotionEvent.requestPermission() !== 'granted') {
      throw new Error('Chưa cấp quyền cảm biến');
    }
    window.addEventListener('devicemotion', onDeviceMotion, { passive: true });
    sensorActive = true;
    sensorAccelerationWarned = false;   // lần bật mới thì được nhắc lại một lần
    if (toggle) {
      setButtonLabel(toggle, 'Dừng cảm biến');
      toggle.setAttribute('aria-pressed', 'true');
    }
    setField($('sensorBadge'), 'ĐANG GỬI');
    const badge = $('sensorBadge');
    if (badge) badge.className = 'badge normal';
    setField($('sensorMeta'), 'Cảm biến hoạt động khi ứng dụng đang mở.');
  } catch (error) {
    setField($('sensorMeta'), error.message);
  }
}

/* ============================== HUẤN LUYỆN =============================== */
async function checkTrainingStatus() {
  const job = await api('/api/training/status');
  if (job.status === 'TRAINING') {
    renderTrainingJob(job);
    if (!trainingTimer) trainingTimer = setInterval(() => ignore(checkTrainingStatus()), 3000);
    return;
  }
  stopTrainingPolling();
  if (job.status === 'READY' && state.calibration?.model_status !== 'READY') {
    state.calibration = await api('/api/calibration');
    renderCalibration(state.calibration);
    await api('/api/metrics').then(renderMetrics).catch(() => {});
  }
  renderTrainingJob(job);
}

function renderTrainingJob(job) {
  const button = $('trainButton');
  if (job.status === 'TRAINING') {
    setField($('trainingTitle'), 'Đang huấn luyện model');
    setField($('trainingMeta'), 'Không tắt máy chủ. Quá trình có thể mất vài phút.');
    if (button) {
      button.disabled = true;
      setButtonLabel(button, 'Đang huấn luyện…');
    }
    return;
  }
  if (button && button.getAttribute('aria-busy') === 'true') setButtonBusy(button, false);
  if (job.status === 'FAILED') {
    setField($('trainingTitle'), 'Huấn luyện thất bại');
    setField($('trainingMeta'), job.message || 'Kiểm tra dữ liệu và thử lại.');
    if (button) {
      button.disabled = false;
      // Đặt nhãn giống hệt renderCalibration để nhịp poll kế tiếp không đổi chữ
      // ngược lại (trước đây nút còn kẹt chữ "Đang huấn luyện…" tới ~2 giây).
      setButtonLabel(button, state.calibration?.model_status === 'READY'
        ? 'Huấn luyện lại model' : 'Huấn luyện model căn nhà');
    }
  }
}

/* ============================== CHIA SẺ NHÀ ============================== */
function renderMembers(members) {
  const list = $('memberList');
  if (!list) return;
  list.innerHTML = members.map(member => `
    <div class="entity-row">
      <div><strong>${escapeHTML(member.display_name)}</strong>
        <small>${escapeHTML(member.email)} • tham gia ${fmtTime(member.joined_at)}</small></div>
      <button type="button" data-kick-member="${member.user_id}"
        aria-label="Xóa quyền xem của ${escapeHTML(member.display_name)}">Xóa quyền</button>
    </div>`).join('') || '<div class="empty-state">Chưa có thành viên nào tham gia.</div>';
  list.querySelectorAll('[data-kick-member]').forEach(button => {
    button.addEventListener('click', () => ignore((async () => {
      if (!confirm('Xóa quyền xem của thành viên này? Điều này không xóa dữ liệu nhà.')) return;
      try {
        renderMembers(await api(`/api/homes/${state.me.active_home.id}/members/${button.dataset.kickMember}`, { method: 'DELETE' }));
      } catch (error) {
        alert(error.message);
      }
    })()));
  });
}

async function openShareDialog() {
  setField($('joinMessage'), '');
  setField($('shareMeta'), '');
  if ($('shareCode')) $('shareCode').value = '';
  const home = state.me?.active_home;
  const isOwner = home?.role !== 'member';
  if ($('ownerShareSection')) $('ownerShareSection').hidden = !isOwner;
  if (isOwner && home) {
    try {
      const { share, ttl_hours } = await api(`/api/homes/${home.id}/share`);
      if ($('shareCode')) $('shareCode').value = share?.code || '';
      setField($('shareMeta'), share
        ? `Mã còn hiệu lực ${Math.round((share.expires_at - Date.now() / 1000) / 3600)} giờ trên tổng ${ttl_hours} giờ.`
        : 'Chưa có mã — bấm “Tạo mã mới”.');
      renderMembers(await api(`/api/homes/${home.id}/members`));
    } catch (error) {
      setField($('shareMeta'), `Không tải được mã chia sẻ: ${error.message}`);
    }
  }
  $('shareDialog')?.showModal();
}

async function copyToClipboard(value, button, originalLabel = 'Sao chép') {
  if (!value || !button) return;
  try {
    await navigator.clipboard.writeText(value);
  } catch {
    const input = button.parentElement?.querySelector('input');
    if (input) { input.select(); document.execCommand('copy'); }
  }
  setButtonLabel(button, 'Đã sao chép');
  setTimeout(() => setButtonLabel(button, originalLabel), 1500);
}

/* ============================== GẮN SỰ KIỆN ============================== */
on('loginTab', 'click', () => selectAuthTab('login'));
on('registerTab', 'click', () => selectAuthTab('register'));
on('loginForm', 'submit', event => {
  event.preventDefault();
  ignore(submitAuth(event.currentTarget, '/api/auth/login'));
});
on('registerForm', 'submit', event => {
  event.preventDefault();
  ignore(submitAuth(event.currentTarget, '/api/auth/register'));
});
on('logoutButton', 'click', () => ignore(api('/api/auth/logout', { method: 'POST' }).then(() => location.reload())));

on('homeSelect', 'change', event => ignore((async () => {
  await api(`/api/homes/${event.target.value}/select`, { method: 'POST' });
  state.me = await api('/api/auth/me');
  renderHomes();
  await loadHome();
})()));

on('addHomeButton', 'click', () => $('homeDialog')?.showModal());
on('shareButton', 'click', () => ignore(openShareDialog()));

on('rotateShareButton', 'click', event => ignore((async () => {
  const button = event.currentTarget;
  setButtonBusy(button, true, 'Đang tạo…');
  try {
    const { share, ttl_hours } = await api(`/api/homes/${state.me.active_home.id}/share`, { method: 'POST' });
    if ($('shareCode')) $('shareCode').value = share.code;
    setField($('shareMeta'), `Mã mới có hiệu lực ${ttl_hours} giờ. Mã cũ đã bị vô hiệu.`);
  } catch (error) {
    alert(error.message);
  } finally {
    setButtonBusy(button, false);
  }
})()));

on('revokeShareButton', 'click', () => ignore((async () => {
  if (!confirm('Thu hồi mã chia sẻ hiện tại? Người chưa nhập mã sẽ không thể tham gia.')) return;
  try {
    await api(`/api/homes/${state.me.active_home.id}/share`, { method: 'DELETE' });
    if ($('shareCode')) $('shareCode').value = '';
    setField($('shareMeta'), 'Đã thu hồi mã.');
  } catch (error) {
    alert(error.message);
  }
})()));

on('copyShareCode', 'click', event => ignore(copyToClipboard($('shareCode').value, event.currentTarget)));

on('joinForm', 'submit', event => ignore((async () => {
  event.preventDefault();
  const button = event.currentTarget.querySelector('[type="submit"]');
  setButtonBusy(button, true, 'Đang tham gia…');
  try {
    await api('/api/homes/join', { method: 'POST', body: JSON.stringify({ code: $('joinCode').value.trim() }) });
    $('shareDialog')?.close();
    if ($('joinCode')) $('joinCode').value = '';
    state.me = await api('/api/auth/me');
    renderHomes();
    await loadHome();
  } catch (error) {
    setField($('joinMessage'), error.message);
  } finally {
    setButtonBusy(button, false);
  }
})()));

document.querySelectorAll('[data-close]').forEach(button => {
  button.addEventListener('click', () => $(button.dataset.close)?.close());
});

on('homeForm', 'submit', event => ignore((async () => {
  event.preventDefault();
  const button = event.currentTarget.querySelector('[type="submit"]');
  setButtonBusy(button, true);
  try {
    await api('/api/homes', { method: 'POST', body: JSON.stringify({ name: $('newHomeName').value }) });
    $('homeDialog')?.close();
    if ($('newHomeName')) $('newHomeName').value = '';
    state.me = await api('/api/auth/me');
    renderHomes();
    await loadHome();
  } catch (error) {
    alert(error.message);
  } finally {
    setButtonBusy(button, false);
  }
})()));

on('roomForm', 'submit', event => ignore((async () => {
  event.preventDefault();
  const button = event.currentTarget.querySelector('button');
  setButtonBusy(button, true);
  try {
    await api('/api/rooms', {
      method: 'POST',
      body: JSON.stringify({ name: $('newRoomName').value, max_dwell_minutes: Number($('newRoomDwell').value) })
    });
    if ($('newRoomName')) $('newRoomName').value = '';
    await loadHome();
  } catch (error) {
    alert(error.message);
  } finally {
    setButtonBusy(button, false);
  }
})()));

on('deviceForm', 'submit', event => ignore((async () => {
  event.preventDefault();
  const button = event.currentTarget.querySelector('button');
  setButtonBusy(button, true);
  try {
    const result = await api('/api/devices', {
      method: 'POST', body: JSON.stringify({ name: $('deviceName').value, platform: 'android' })
    });
    if ($('deviceToken')) $('deviceToken').value = result.token;
    if ($('tokenReveal')) $('tokenReveal').hidden = false;
    state.devices = await api('/api/devices');
    renderDevices();
    renderCalibration(state.calibration);
  } catch (error) {
    alert(error.message);
  } finally {
    setButtonBusy(button, false);
  }
})()));

on('copyToken', 'click', event => ignore(copyToClipboard($('deviceToken').value, event.currentTarget)));

on('trainButton', 'click', event => ignore((async () => {
  const button = event.currentTarget;
  setButtonBusy(button, true, 'Đang khởi động…');
  try {
    await api('/api/training/start', { method: 'POST' });
    await checkTrainingStatus();
  } catch (error) {
    alert(error.message);
    setButtonBusy(button, false);
  }
})()));

on('demoFromLock', 'click', startDemo);
on('demoToggle', 'click', toggleDemo);
on('sensorToggle', 'click', () => ignore(toggleSensor()));

on('resetBtn', 'click', event => ignore((async () => {
  if (!confirm('Đặt lại trạng thái tạm thời? Dữ liệu SQLite vẫn được giữ.')) return;
  const button = event.currentTarget;
  button.disabled = true;
  try {
    await api('/api/reset', { method: 'POST' });
    stopDemo();
    if (state.calibration) renderCalibration(state.calibration);
    await refreshDashboard();
    setField($('demoStatus'), 'Đã đặt lại trạng thái tạm thời.');
  } catch (error) {
    alert(error.message);
  } finally {
    button.disabled = false;
  }
})()));

on('installButton', 'click', () => $('installGuide')?.showModal());

/* Ô phòng: chỉ trang demo cũ mới mô phỏng theo phòng được, vì /api/demo/scan
   chỉ chấp nhận tên phòng trong config tổng hợp, không phải tên phòng tự đặt. */
if (!$('roomGrid')) {
  document.querySelectorAll('.floorplan .room-tile').forEach(button => {
    button.addEventListener('click', () => ignore(selectDemoRoom(button.dataset.room)));
  });
}

document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    stopDemo();
    stopPolling();
  } else {
    if (state.authenticated && !pollTimer) startPolling();
    ignore(refreshDashboard());
  }
});

window.addEventListener('pagehide', () => {
  stopDemo();
  stopPolling();
  stopTrainingPolling();
});

/* Cài trên iPhone: chỉ hiện nút khi đang ở Safari iOS và chưa thêm vào MH chính. */
const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
const isStandalone = matchMedia('(display-mode: standalone)').matches || navigator.standalone;
if (isIOS && !isStandalone && $('installButton')) $('installButton').hidden = false;

if ('serviceWorker' in navigator) navigator.serviceWorker.register('/service-worker.js').catch(console.error);

/* ============================== BOOT ===================================== */
if ($('appShell') && $('authView')) {
  // dashboard.html — cần phiên đăng nhập
  ignore(loadApplication().catch(error => {
    console.error(error);
    showAuth(false);
  }));
} else {
  // index.html — trang demo tĩnh, không có tài khoản
  state.authenticated = true;
  ignore(api('/api/metrics').then(renderMetrics).catch(() => renderMetrics({})));
  ignore(refreshDashboard());
  startPolling();
}
