/* =============================================================================
 * An Tâm Home — dashboard và kết nối realtime
 * -----------------------------------------------------------------------------
 * Nạp phiên, chọn căn nhà, giữ SSE (fallback polling) và nối các module lại
 * với nhau. Đây là tầng cao nhất trước `main.js`; không module nào import ngược
 * file này, nên đồ thị import không có vòng.
 * ========================================================================== */
import {
  $, POLL_MS, STREAM_RETRY_MS, api, escapeHTML, ignore, registerStop, state
} from './core.js';
import { showAuth } from './auth.js';
import { renderCalibration, renderDevices, renderRooms } from './settings.js';
import {
  applyAlerts, applyHistory, applyStatus, refreshDashboard, renderMetrics, resetRenderCache, setConnection
} from './monitoring.js';
import { checkTrainingStatus } from './training.js';

let pollTimer = null;
let stream = null;
let streamRetryTimer = null;

export async function loadApplication() {
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
}

/**
 * Ưu tiên SSE: một kết nối giữ mở, máy chủ đẩy status/history/alerts.
 * Trình duyệt không hỗ trợ EventSource (hoặc stream lỗi) thì quay về polling.
 */
export function startLiveUpdates() {
  if (!state.authenticated) return;
  stopStream();
  if (typeof EventSource !== 'function') {
    startPolling();
    return;
  }
  startStream();
}

function startStream() {
  if (!state.authenticated || document.hidden || stream) return;
  let source;
  try {
    source = new EventSource('/api/stream');
  } catch (error) {
    console.error('[An Tâm] không mở được SSE:', error);
    startPolling();
    scheduleStreamRetry();
    return;
  }
  stream = source;
  source.addEventListener('open', () => {
    if (stream !== source) return;
    stopPolling();
    setConnection(true);
  });
  source.addEventListener('status', event => {
    const payload = parseStreamEvent(event);
    if (payload) applyStatus(payload);
  });
  source.addEventListener('history', event => {
    const payload = parseStreamEvent(event);
    if (payload) applyHistory(payload);
  });
  source.addEventListener('alerts', event => {
    const payload = parseStreamEvent(event);
    if (payload) applyAlerts(payload);
  });
  // Chủ nhà gỡ thành viên hoặc xóa nhà: nạp lại phiên để không hiển thị
  // tiếp dữ liệu của nhà mà mình không còn quyền xem.
  source.addEventListener('auth', () => {
    stopLiveUpdates();
    location.reload();
  });
  source.addEventListener('error', () => handleStreamError(source));
}

function parseStreamEvent(event) {
  try {
    return JSON.parse(event.data);
  } catch (error) {
    console.error('[An Tâm] SSE trả dữ liệu không hợp lệ:', error);
    return null;
  }
}

function handleStreamError(source) {
  if (stream !== source) return;
  source.close();
  stream = null;
  if (!state.authenticated) return;
  // EventSource không cho biết lỗi mạng hay 401. Polling vừa giữ dữ liệu
  // tươi trong lúc chờ, vừa phát hiện phiên hết hạn để hiện form đăng nhập.
  startPolling();
  scheduleStreamRetry();
}

function scheduleStreamRetry() {
  if (streamRetryTimer || !state.authenticated) return;
  streamRetryTimer = setTimeout(() => {
    streamRetryTimer = null;
    if (state.authenticated && !document.hidden) startStream();
  }, STREAM_RETRY_MS);
}

function stopStream() {
  if (stream) {
    stream.close();
    stream = null;
  }
  if (streamRetryTimer) {
    clearTimeout(streamRetryTimer);
    streamRetryTimer = null;
  }
}

export function startPolling() {
  stopPolling();
  pollTimer = setInterval(() => ignore(refreshDashboard()), POLL_MS);
}

function stopPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = null;
}

export function stopLiveUpdates() {
  stopStream();
  stopPolling();
}

export function renderHomes() {
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

export async function loadHome() {
  // Đóng stream cũ trước khi nạp nhà mới: generator phía server giữ `home`
  // của lúc kết nối, nên nếu để mở sẽ tiếp tục đẩy dữ liệu nhà cũ.
  stopStream();
  try {
    await loadHomeData();
  } finally {
    if (state.authenticated) startLiveUpdates();
  }
}

async function loadHomeData() {
  const [rooms, devices, calibration] = await Promise.all([
    api('/api/rooms'), api('/api/devices'), api('/api/calibration')
  ]);
  state.rooms = rooms;
  state.devices = devices;
  state.calibration = calibration;
  state.demoMode = false;
  state.lastRoom = null;
  state.lastSafety = null;
  resetRenderCache();
  document.body.classList.remove('demo-mode');
  renderRooms(loadHome);
  renderDevices();
  renderCalibration(calibration);
  await Promise.all([
    refreshDashboard(),
    api('/api/metrics').then(renderMetrics).catch(() => renderMetrics({}))
  ]);
  ignore(checkTrainingStatus());
}

registerStop(stopLiveUpdates);
