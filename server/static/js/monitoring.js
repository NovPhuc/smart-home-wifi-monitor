/* =============================================================================
 * An Tâm Home — giám sát
 * -----------------------------------------------------------------------------
 * Vẽ payload status/history/alerts/metrics và giữ nhịp polling dự phòng.
 * SSE trong dashboard gọi thẳng các hàm `apply*` khi có event mới.
 * ========================================================================== */
import {
  $, ACTIVITY, ALERT_LIMIT, HISTORY_LIMIT, SAFETY_COPY, SIGNAL_COPY, STALE_AFTER_S, api,
  escapeHTML, fmtDuration, fmtTime, ignore, pulse, roomLabel, setBar, setField, state, translateReason
} from './core.js';
import { showAuth } from './auth.js';
import { applyActiveRoom, renderCalibration } from './settings.js';
import { renderMobileSensor } from './sensor.js';

let refreshInFlight = false;
let refreshPending = false;
const lastRenderKey = { status: '', history: '', alerts: '' };

/** Xóa cache vẽ khi đổi căn nhà để payload giống nhau vẫn được vẽ lại. */
export function resetRenderCache() {
  lastRenderKey.status = lastRenderKey.history = lastRenderKey.alerts = '';
}

export function setConnection(ok, timestamp) {
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

export function renderMetrics(metrics = {}) {
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

/** Vẽ payload status — dùng chung cho SSE và polling dự phòng. */
export function applyStatus(status) {
  setConnection(true, status.timestamp);
  const statusKey = JSON.stringify([
    status.room, status.status, status.confidence, status.dwell_minutes, status.anomaly_score,
    status.timestamp, status.activity, status.signal, status.smoothed_probabilities,
    status.calibration, status.mobile_sensor
  ]);
  if (statusKey !== lastRenderKey.status && safeRender('trạng thái', () => renderStatus(status))) {
    lastRenderKey.status = statusKey;
  }
}

export function applyHistory(history) {
  const historyKey = JSON.stringify(history.map(item => [item.timestamp, item.room, item.dwell_minutes, item.activity?.state]));
  if (historyKey !== lastRenderKey.history && safeRender('dòng thời gian', () => renderHistory(history))) {
    lastRenderKey.history = historyKey;
  }
}

export function applyAlerts(alerts) {
  const alertsKey = JSON.stringify(alerts.map(item => [item.id, item.status]));
  if (alertsKey !== lastRenderKey.alerts && safeRender('cảnh báo', () => renderAlerts(alerts))) {
    lastRenderKey.alerts = alertsKey;
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
export async function refreshDashboard() {
  if ($('appShell') && !state.authenticated) return;
  if (document.hidden) return;
  if (refreshInFlight) { refreshPending = true; return; }
  refreshInFlight = true;
  try {
    const [status, history, alerts] = await Promise.all([
      api('/api/status'), api('/api/history'), api('/api/alerts')
    ]);
    applyStatus(status);
    applyHistory(history);
    applyAlerts(alerts);
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
