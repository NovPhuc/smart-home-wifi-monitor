/* =============================================================================
 * An Tâm Home — cảm biến điện thoại
 * -----------------------------------------------------------------------------
 * Gửi gia tốc kế lên /api/sensor khi người dùng bật cảm biến. Chỉ hoạt động
 * trong lúc tab đang mở và cần HTTPS trên iOS.
 * ========================================================================== */
import {
  $, SENSOR_COPY, api, deviceId, fmtTime, ignore, setButtonLabel, setField
} from './core.js';

let sensorActive = false;
let lastSensorSentAt = 0;
/** Cảnh báo "không có gia tốc tuyến tính" chỉ nói một lần cho mỗi lần bật cảm biến. */
let sensorAccelerationWarned = false;

export function renderMobileSensor(sensor) {
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

export async function toggleSensor() {
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
