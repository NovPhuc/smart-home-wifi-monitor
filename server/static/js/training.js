/* =============================================================================
 * An Tâm Home — huấn luyện model
 * -----------------------------------------------------------------------------
 * Hỏi trạng thái job mỗi 3 giây khi đang TRAINING; xong thì nạp lại calibration
 * và metrics để dashboard không phải tải lại trang.
 * ========================================================================== */
import {
  $, api, ignore, registerStop, setButtonBusy, setButtonLabel, setField, state
} from './core.js';
import { renderMetrics } from './monitoring.js';
import { renderCalibration } from './settings.js';

let trainingTimer = null;

export async function checkTrainingStatus() {
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

export function renderTrainingJob(job) {
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

export function stopTrainingPolling() {
  if (trainingTimer) clearInterval(trainingTimer);
  trainingTimer = null;
}

registerStop(stopTrainingPolling);
