const POLL_MS = 1500;
const ROOM_NAMES = {
  Bedroom: 'Phòng ngủ',
  Corridor: 'Hành lang',
  Bathroom: 'Phòng tắm',
  LivingRoom: 'Phòng khách',
  Kitchen: 'Nhà bếp'
};
const ACTIVITY = {
  CALIBRATING: ['Đang hiệu chuẩn', 'Cần vài mẫu tín hiệu đầu tiên', 'CAL'],
  STILL: ['Đang nghỉ ngơi', 'Không ghi nhận biến động đáng kể', 'YÊN'],
  LIGHT_ACTIVITY: ['Hoạt động nhẹ', 'Tín hiệu thay đổi nhẹ trong phòng', 'NHẸ'],
  MOVING: ['Đang di chuyển', 'Phát hiện biến động tín hiệu Wi-Fi', 'ĐI'],
  ROOM_CHANGE: ['Vừa chuyển phòng', 'Đã xác nhận thay đổi vị trí', 'ĐỔI']
};

let demoTimer = null;
let sensorActive = false;
let lastSensorSentAt = 0;
const deviceId = localStorage.getItem('an-tam-device-id') || `iphone-${crypto.randomUUID?.() || Date.now()}`;
localStorage.setItem('an-tam-device-id', deviceId);

const $ = id => document.getElementById(id);
const escapeHTML = value => String(value ?? '').replace(/[&<>'"]/g, character => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
})[character]);

function fmtTime(timestamp) {
  return timestamp
    ? new Date(timestamp * 1000).toLocaleTimeString('vi-VN', {hour: '2-digit', minute: '2-digit'})
    : '—';
}

function fmtDuration(minutes) {
  if (minutes == null) return '—';
  if (minutes < 1) return `${Math.round(minutes * 60)} giây`;
  if (minutes < 60) return `${minutes.toFixed(1)} phút`;
  return `${Math.floor(minutes / 60)}g ${Math.round(minutes % 60)}p`;
}

function translateReason(reason) {
  return String(reason || '')
    .replace('High trajectory reconstruction error', 'Quỹ đạo di chuyển có sai số tái tạo cao')
    .replace(/^Long dwell in ([^:]+):/, 'Ở $1 quá lâu:')
    .replace(/^Impossible\/unlikely transition:/, 'Chuyển phòng không phù hợp topology:')
    .replace(/^Unusual nighttime dwell in ([^:]+):/, 'Lưu trú ban đêm bất thường tại $1:')
    .replace(/^Unusual nighttime movement:/, 'Di chuyển ban đêm bất thường:')
    .replace(/^No detected movement for/, 'Không phát hiện vận động trong')
    .replace('Possible impact followed by low motion; caregiver review required', 'Ghi nhận va chạm rồi ít vận động; cần người chăm sóc kiểm tra');
}

async function loadJSON(url, options) {
  const response = await fetch(url + (options ? '' : `?t=${Date.now()}`), options);
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

function setConnection(ok, timestamp) {
  const stale = timestamp && Date.now() / 1000 - timestamp > 15;
  $('statusDot').className = ok && !stale ? 'live' : 'error';
  $('statusText').textContent = !ok ? 'Mất kết nối' : stale ? 'Dữ liệu đã cũ' : 'Hệ thống trực tuyến';
}

function renderMobileSensor(sensor) {
  if (!sensor) return;
  const labels = {
    MOVING: 'Đang di chuyển',
    STILL: 'Đang đứng yên',
    IMPACT_RECORDED: 'Đã ghi nhận va chạm',
    NO_DATA: 'Chưa có dữ liệu'
  };
  $('sensorBadge').textContent = labels[sensor.state] || sensor.state;
  $('sensorBadge').className = `badge ${sensor.possible_impact ? 'warning' : sensor.state === 'NO_DATA' ? 'neutral' : 'normal'}`;
  if (sensor.last_seen_at) {
    $('sensorMeta').textContent = `${sensor.samples_received} mẫu • biên độ ${Number(sensor.motion_magnitude).toFixed(2)} m/s² • ${fmtTime(sensor.last_seen_at)}`;
  }
}

function renderStatus(status) {
  const roomName = ROOM_NAMES[status.room] || status.room || 'Chưa có dữ liệu';
  $('room').textContent = roomName;
  $('roomMeta').textContent = status.room ? `${status.room} • định vị mức phòng` : 'Đang chờ fingerprint Wi-Fi…';
  $('confidence').textContent = status.confidence != null ? `TIN CẬY ${(status.confidence * 100).toFixed(0)}%` : '—';
  $('dwell').textContent = fmtDuration(status.dwell_minutes);
  $('score').textContent = status.anomaly_score != null ? status.anomaly_score.toFixed(3) : 'Đang học';
  const ratio = status.anomaly_score != null && status.anomaly_threshold
    ? Math.min(100, status.anomaly_score / status.anomaly_threshold * 100)
    : 0;
  $('meterFill').style.width = `${ratio}%`;

  const activity = status.activity || {};
  const copy = ACTIVITY[activity.state] || ACTIVITY.CALIBRATING;
  $('activityState').textContent = copy[0];
  $('activityMeta').textContent = copy[1];
  $('activityIcon').textContent = copy[2];
  $('transitions').textContent = activity.transitions_last_hour ?? '—';

  const state = (status.status || 'NO_DATA').toUpperCase();
  $('safetyCard').className = `card safety-card ${state.toLowerCase()}`;
  $('systemBadge').className = `badge ${state === 'NO_DATA' ? 'neutral' : state.toLowerCase()}`;
  $('systemBadge').textContent = {
    NORMAL: 'AN TOÀN', WARNING: 'CẦN CHÚ Ý', CRITICAL: 'KHẨN CẤP', NO_DATA: 'CHƯA CÓ DỮ LIỆU'
  }[state] || state;
  $('safetyIcon').textContent = state === 'CRITICAL' ? '!!' : state === 'WARNING' ? '!' : 'OK';
  $('safetyTitle').textContent = state === 'CRITICAL'
    ? 'Phát hiện bất thường nghiêm trọng'
    : state === 'WARNING'
      ? 'Có dấu hiệu cần kiểm tra'
      : state === 'NORMAL' ? 'Sinh hoạt bình thường' : 'Hệ thống sẵn sàng';
  $('safetyDescription').textContent = translateReason((status.reasons || [])[0]) || 'Không có cảnh báo cần xử lý.';

  document.querySelectorAll('.room-tile').forEach(element => {
    element.classList.toggle('active', element.dataset.room === status.room);
    element.setAttribute('aria-pressed', element.dataset.room === status.room ? 'true' : 'false');
  });
  const probabilities = status.smoothed_probabilities || {};
  $('probabilities').innerHTML = Object.entries(probabilities).map(([room, probability]) =>
    `<div class="probability"><span>${escapeHTML(ROOM_NAMES[room] || room)} ${(probability * 100).toFixed(0)}%</span><div><i style="width:${probability * 100}%"></i></div></div>`
  ).join('');

  const signal = status.signal || {};
  $('signalDot').className = (signal.quality || '').toLowerCase();
  const qualityText = {GOOD: 'Tín hiệu tốt', FAIR: 'Tín hiệu vừa', WEAK: 'Tín hiệu yếu'};
  $('signalText').textContent = signal.quality
    ? `${signal.visible_access_points} AP • ${qualityText[signal.quality] || signal.quality}`
    : 'Chưa có tín hiệu';
  $('lastUpdate').textContent = fmtTime(status.timestamp);
  renderMobileSensor(status.mobile_sensor);
}

function compactHistory(history) {
  const result = [];
  for (const item of history) {
    const last = result[result.length - 1];
    if (!last || last.room !== item.room) result.push(item);
    else result[result.length - 1] = item;
  }
  return result.slice(-12).reverse();
}

function renderHistory(history) {
  const items = compactHistory(history);
  $('historyCount').textContent = `${items.length} sự kiện`;
  $('history').innerHTML = items.map((item, index) =>
    `<div class="timeline-item ${index < items.length - 1 ? 'transition' : ''}"><time>${fmtTime(item.timestamp)}</time><strong>${escapeHTML(ROOM_NAMES[item.room] || item.room)}</strong><span>${item.activity?.state === 'ROOM_CHANGE' ? 'Chuyển phòng' : fmtDuration(item.dwell_minutes)}</span></div>`
  ).join('') || '<div class="empty-state">Dữ liệu hoạt động sẽ xuất hiện tại đây.</div>';
}

function renderAlerts(alerts) {
  $('alertCount').textContent = alerts.length;
  $('alertsList').innerHTML = alerts.slice(-6).reverse().map(item => {
    const location = ROOM_NAMES[item.room] || item.room || 'Cảm biến iPhone';
    const reasons = (item.reasons || []).map(translateReason).join(' · ');
    return `<div class="alert ${(item.status || '').toLowerCase()}"><strong>${escapeHTML(location)} • ${escapeHTML(item.status)}</strong><span>${escapeHTML(reasons)}</span></div>`;
  }).join('') || '<div class="empty-state">Chưa có cảnh báo.</div>';
}

function renderMetrics(metrics) {
  const room = metrics.room_model || {};
  const anomaly = metrics.anomaly_model || {};
  $('metricAccuracy').textContent = room.accuracy != null ? `${(room.accuracy * 100).toFixed(2)}%` : '—';
  $('metricF1').textContent = room.macro_f1 != null ? `${(room.macro_f1 * 100).toFixed(2)}%` : '—';
  $('metricRecall').textContent = anomaly.recall != null ? `${(anomaly.recall * 100).toFixed(2)}%` : '—';
  $('metricLatency').textContent = room.mean_inference_ms != null ? `${room.mean_inference_ms.toFixed(3)} ms` : '—';
  const comparisons = [
    ['RoomNet-Lite', room.accuracy],
    ...Object.entries(metrics.baselines || {}).map(([name, values]) => [name, values.accuracy])
  ].filter(([, value]) => value != null);
  $('baselineComparison').innerHTML = comparisons.map(([name, value]) =>
    `<div><span>${escapeHTML(name)}</span><div><i style="width:${value * 100}%"></i></div><strong>${(value * 100).toFixed(2)}%</strong></div>`
  ).join('');
}

async function refresh() {
  if (document.hidden) return;
  try {
    const [status, history, alerts] = await Promise.all([
      loadJSON('/api/status'), loadJSON('/api/history'), loadJSON('/api/alerts')
    ]);
    renderStatus(status);
    renderHistory(history);
    renderAlerts(alerts);
    setConnection(true, status.timestamp);
  } catch (error) {
    console.error(error);
    setConnection(false);
  }
}

async function demoStep(room) {
  try {
    await loadJSON('/api/demo/scan', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(room ? {room} : {})
    });
    await refresh();
  } catch (error) {
    stopDemo();
    $('demoStatus').textContent = `Không thể chạy demo: ${error.message}`;
  }
}

function stopDemo() {
  if (demoTimer) clearInterval(demoTimer);
  demoTimer = null;
  $('demoToggle').classList.remove('running');
  $('demoToggle').textContent = 'Chạy demo';
  $('demoToggle').setAttribute('aria-pressed', 'false');
}

function toggleDemo() {
  if (demoTimer) {
    stopDemo();
    $('demoStatus').textContent = 'Đã tạm dừng mô phỏng.';
    return;
  }
  $('demoToggle').classList.add('running');
  $('demoToggle').textContent = 'Dừng demo';
  $('demoToggle').setAttribute('aria-pressed', 'true');
  $('demoStatus').textContent = 'Đang phát fingerprint mẫu…';
  demoStep();
  demoTimer = setInterval(() => demoStep(), 900);
}

async function selectDemoRoom(room) {
  stopDemo();
  document.querySelectorAll('.room-tile').forEach(button => { button.disabled = true; });
  $('demoStatus').textContent = `Đang mô phỏng ${ROOM_NAMES[room] || room}…`;
  try {
    for (let index = 0; index < 6; index += 1) await demoStep(room);
    $('demoStatus').textContent = `Đã gửi fingerprint của ${ROOM_NAMES[room] || room}.`;
  } finally {
    document.querySelectorAll('.room-tile').forEach(button => { button.disabled = false; });
  }
}

async function sendMotion(acceleration) {
  try {
    const sensor = await loadJSON('/api/sensor', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({device_id: deviceId, timestamp: Date.now() / 1000, acceleration})
    });
    renderMobileSensor(sensor);
  } catch (error) {
    $('sensorMeta').textContent = `Không gửi được dữ liệu: ${error.message}`;
  }
}

function onDeviceMotion(event) {
  const acceleration = event.acceleration;
  if (!acceleration || acceleration.x == null || acceleration.y == null || acceleration.z == null) {
    $('sensorMeta').textContent = 'Thiết bị không cung cấp gia tốc tuyến tính.';
    return;
  }
  const magnitude = Math.hypot(acceleration.x, acceleration.y, acceleration.z);
  const now = performance.now();
  if (magnitude < 18 && now - lastSensorSentAt < 500) return;
  lastSensorSentAt = now;
  sendMotion({x: acceleration.x, y: acceleration.y, z: acceleration.z});
}

async function toggleSensor() {
  if (sensorActive) {
    window.removeEventListener('devicemotion', onDeviceMotion);
    sensorActive = false;
    $('sensorToggle').textContent = 'Bật cảm biến iPhone';
    $('sensorToggle').setAttribute('aria-pressed', 'false');
    $('sensorBadge').textContent = 'TẮT';
    $('sensorBadge').className = 'badge neutral';
    $('sensorMeta').textContent = 'Đã dừng gửi dữ liệu cảm biến.';
    return;
  }
  if (!window.isSecureContext) {
    $('sensorMeta').textContent = 'Cần mở ứng dụng bằng HTTPS để Safari cấp quyền cảm biến.';
    return;
  }
  if (typeof DeviceMotionEvent === 'undefined') {
    $('sensorMeta').textContent = 'Trình duyệt này không hỗ trợ DeviceMotion.';
    return;
  }
  try {
    if (typeof DeviceMotionEvent.requestPermission === 'function') {
      const permission = await DeviceMotionEvent.requestPermission();
      if (permission !== 'granted') throw new Error('Người dùng chưa cấp quyền cảm biến');
    }
    window.addEventListener('devicemotion', onDeviceMotion, {passive: true});
    sensorActive = true;
    $('sensorToggle').textContent = 'Dừng cảm biến';
    $('sensorToggle').setAttribute('aria-pressed', 'true');
    $('sensorBadge').textContent = 'ĐANG GỬI';
    $('sensorBadge').className = 'badge normal';
    $('sensorMeta').textContent = 'Cảm biến chỉ hoạt động khi ứng dụng đang mở.';
  } catch (error) {
    $('sensorMeta').textContent = error.message;
  }
}

function setupInstallGuide() {
  const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
  const isStandalone = window.matchMedia('(display-mode: standalone)').matches || navigator.standalone;
  if (isIOS && !isStandalone) $('installButton').hidden = false;
  $('installButton').addEventListener('click', () => $('installGuide').showModal());
}

$('demoToggle').addEventListener('click', toggleDemo);
$('sensorToggle').addEventListener('click', toggleSensor);
$('resetBtn').addEventListener('click', async () => {
  if (!window.confirm('Đặt lại toàn bộ phiên giám sát và cảnh báo hiện tại?')) return;
  stopDemo();
  $('resetBtn').disabled = true;
  try {
    await loadJSON('/api/reset', {method: 'POST'});
    $('demoStatus').textContent = 'Đã đặt lại phiên giám sát.';
    await refresh();
  } finally {
    $('resetBtn').disabled = false;
  }
});
document.querySelectorAll('.room-tile').forEach(button => {
  button.addEventListener('click', () => selectDemoRoom(button.dataset.room));
});
document.addEventListener('visibilitychange', () => {
  if (document.hidden) stopDemo();
  else refresh();
});

setupInstallGuide();
if ('serviceWorker' in navigator) navigator.serviceWorker.register('/service-worker.js').catch(console.error);
loadJSON('/api/metrics').then(renderMetrics).catch(console.error);
refresh();
setInterval(refresh, POLL_MS);
