/* =============================================================================
 * An Tâm Home — xác thực
 * -----------------------------------------------------------------------------
 * Chỉ phụ trách form đăng nhập/đăng ký và chuyển đổi hai tab. Việc nạp lại
 * dashboard sau khi đăng nhập được truyền vào qua `onSuccess` để module này
 * không phải import ngược tầng dashboard.
 * ========================================================================== */
import { $, api, setButtonBusy, state, stopAllActivity } from './core.js';

export function showAuth(register = false) {
  state.authenticated = false;
  if ($('authView')) $('authView').hidden = false;
  if ($('appShell')) $('appShell').hidden = true;
  selectAuthTab(register ? 'register' : 'login');
  stopAllActivity();
}

export function selectAuthTab(name) {
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

export async function submitAuth(form, endpoint, onSuccess) {
  clearFieldErrors(form);
  if ($('authError')) $('authError').hidden = true;
  if (!form.reportValidity()) return;
  const button = form.querySelector('button[type="submit"]');
  setButtonBusy(button, true);
  try {
    await api(endpoint, { method: 'POST', body: JSON.stringify(Object.fromEntries(new FormData(form).entries())) });
    form.reset();
    await onSuccess();
  } catch (error) {
    const wrongCredentials = error.data?.error === 'INVALID_CREDENTIALS';
    showAuthErrors(form, wrongCredentials ? 'Email hoặc mật khẩu không đúng' : 'Vui lòng kiểm tra thông tin.',
      error.data?.fields || {});
  } finally {
    setButtonBusy(button, false);
  }
}
