function setStatus(type, msg) {
  const el = document.getElementById('status');
  el.innerHTML = type==='loading' ? `<div class="spinner"></div>${msg}` : `<span>${msg}</span>`;
}
function showError(msg) {
  document.getElementById('jobs').innerHTML = `<div class="error-box">❌ ${esc(msg)}</div>`;
}
function esc(str) {
  return String(str||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
