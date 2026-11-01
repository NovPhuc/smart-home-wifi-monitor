/* =============================================================================
 * An Tâm Home — thiết lập căn nhà
 * -----------------------------------------------------------------------------
 * Phòng, thiết bị đã ghép và tiến độ thu dữ liệu. Các thao tác đổi phòng nhận
 * `reloadHome` từ tầng dashboard để không import ngược module nạp dữ liệu.
 * ========================================================================== */
import {
  $, DEMO_ROOM_NAMES, REDUCED_MOTION, api, escapeHTML, fmtTime, ignore, pulse,
  setBar, setButtonLabel, setField, state
} from './core.js';

export function renderRooms(reloadHome) {
  const list = $('roomList');
  if (list) {
    list.innerHTML = state.rooms.map(room => `
      <div class="entity-row">
        <div><strong>${escapeHTML(room.name)}</strong>
          <small>Cảnh báo lưu trú sau ${room.max_dwell_minutes} phút</small></div>
        <div class="row-actions">
          <button type="button" class="secondary" data-rename-room="${room.id}"
            aria-label="Đổi tên phòng ${escapeHTML(room.name)}">Đổi tên</button>
          <button type="button" data-delete-room="${room.id}"
            aria-label="Xóa phòng ${escapeHTML(room.name)}">Xóa</button>
        </div>
      </div>`).join('') || '<div class="empty-state">Chưa có phòng. Hãy thêm ít nhất hai phòng.</div>';
    list.querySelectorAll('[data-rename-room]').forEach(button => {
      const room = state.rooms.find(item => item.id === Number(button.dataset.renameRoom));
      if (room) button.addEventListener('click', () => ignore(renameRoom(room, reloadHome)));
    });
    list.querySelectorAll('[data-delete-room]').forEach(button => {
      button.addEventListener('click', () => ignore(deleteRoom(Number(button.dataset.deleteRoom), reloadHome)));
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

export function renderRoomGrid() {
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

export function applyActiveRoom(room) {
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

export function renderDevices() {
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

export function renderCalibration(calibration) {
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

async function renameRoom(room, reloadHome) {
  const name = prompt('Tên phòng mới:', room.name);
  if (name === null) return;
  const trimmed = name.trim();
  if (!trimmed || trimmed === room.name) return;
  // PATCH mặc định max_dwell_minutes=60 nếu thiếu, nên gửi lại giá trị cũ
  // để đổi tên không âm thầm đổi ngưỡng cảnh báo lưu trú.
  await api(`/api/rooms/${room.id}`, {
    method: 'PATCH',
    body: JSON.stringify({ name: trimmed, max_dwell_minutes: room.max_dwell_minutes })
  });
  await reloadHome();
}

async function deleteRoom(id, reloadHome) {
  if (!confirm('Xóa phòng sẽ xóa toàn bộ scan đã thu của phòng này. Tiếp tục?')) return;
  await api(`/api/rooms/${id}`, { method: 'DELETE' });
  await reloadHome();
}

async function revokeDevice(id) {
  if (!confirm('Thu hồi mã ghép nối của thiết bị này?')) return;
  await api(`/api/devices/${id}`, { method: 'DELETE' });
  state.devices = await api('/api/devices');
  renderDevices();
  renderCalibration(state.calibration);
}
