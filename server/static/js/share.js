/* =============================================================================
 * An Tâm Home — chia sẻ căn nhà
 * -----------------------------------------------------------------------------
 * Mã mời, danh sách thành viên và thao tác sao chép. Không phụ thuộc module
 * dashboard để tránh vòng import.
 * ========================================================================== */
import {
  $, api, escapeHTML, fmtTime, ignore, setButtonLabel, setField, state
} from './core.js';

export function renderMembers(members) {
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

export async function openShareDialog() {
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

export async function copyToClipboard(value, button, originalLabel = 'Sao chép') {
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
