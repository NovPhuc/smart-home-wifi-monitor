/* =============================================================================
 * An Tâm Home — điểm vào giao diện
 * -----------------------------------------------------------------------------
 * Gắn sự kiện cho cả dashboard.html và index.html, đăng ký service worker và
 * khởi động ứng dụng. Mọi xử lý nằm trong các module js/ tương ứng.
 * ========================================================================== */
import {
  $, api, ignore, on, setButtonBusy, setField, state
} from './core.js';
import { selectAuthTab, showAuth, submitAuth } from './auth.js';
import {
  loadApplication, loadHome, renderHomes, startLiveUpdates, startPolling, stopLiveUpdates
} from './dashboard.js';
import { renderCalibration, renderDevices } from './settings.js';
import { refreshDashboard, renderMetrics } from './monitoring.js';
import { selectDemoRoom, startDemo, stopDemo, toggleDemo } from './demo.js';
import { toggleSensor } from './sensor.js';
import { checkTrainingStatus, stopTrainingPolling } from './training.js';
import { copyToClipboard, openShareDialog } from './share.js';

on('loginTab', 'click', () => selectAuthTab('login'));
on('registerTab', 'click', () => selectAuthTab('register'));
on('loginForm', 'submit', event => {
  event.preventDefault();
  ignore(submitAuth(event.currentTarget, '/api/auth/login', loadApplication));
});
on('registerForm', 'submit', event => {
  event.preventDefault();
  ignore(submitAuth(event.currentTarget, '/api/auth/register', loadApplication));
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
    stopLiveUpdates();
  } else {
    if (state.authenticated) startLiveUpdates();
    ignore(refreshDashboard());
  }
});

window.addEventListener('pagehide', () => {
  stopDemo();
  stopLiveUpdates();
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
