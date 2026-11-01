/* =============================================================================
 * An Tâm Home — entry point
 * -----------------------------------------------------------------------------
 * Toàn bộ giao diện đã được tách thành ES module trong thư mục js/. File này
 * giữ nguyên đường dẫn /static/app.js để template, service worker và bookmark
 * cũ không phải đổi.
 *
 * Dùng import động thay vì `import ... from` để HTML cũ (nạp app.js như script
 * thường, chưa có type="module") vẫn không vỡ cú pháp khi service worker cập
 * nhật file này trước template.
 * ========================================================================== */
import('/static/js/main.js').catch(error => {
  console.error('[An Tâm] không nạp được giao diện:', error);
});
