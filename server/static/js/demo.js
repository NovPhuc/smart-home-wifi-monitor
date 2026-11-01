/* =============================================================================
 * An Tâm Home — demo
 * -----------------------------------------------------------------------------
 * Phát fingerprint mẫu theo nhịp, hoặc bấm một ô phòng để gửi mẫu của phòng đó.
 * ========================================================================== */
import {
  $, DEMO_STEP_MS, api, ignore, registerStop, roomLabel, setButtonLabel, setField, state
} from './core.js';
import { refreshDashboard } from './monitoring.js';
import { renderCalibration, renderRoomGrid } from './settings.js';

let demoTimer = null;

async function demoStep(room) {
  await api('/api/demo/scan', { method: 'POST', body: JSON.stringify(room ? { room } : {}) });
  await refreshDashboard();
}

export function stopDemo() {
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

export function startDemo() {
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

export function toggleDemo() {
  if (demoTimer) {
    stopDemo();
    setField($('demoStatus'), 'Đã tạm dừng demo.');
  } else {
    startDemo();
  }
}

/** Trang demo cũ: bấm một ô phòng để gửi 6 fingerprint của đúng phòng đó. */
export async function selectDemoRoom(room) {
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

registerStop(stopDemo);
