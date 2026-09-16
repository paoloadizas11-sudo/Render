/* ── Toast ────────────────────────────────────────── */
function toast(msg, ok = true) {
  const t = document.createElement('div');
  t.textContent = msg;
  t.style.cssText = `
    position:fixed;bottom:24px;right:24px;z-index:9999;
    background:${ok ? 'rgba(16,185,129,.12)' : 'rgba(239,68,68,.12)'};
    border:1px solid ${ok ? 'rgba(16,185,129,.3)' : 'rgba(239,68,68,.3)'};
    color:${ok ? '#10B981' : '#EF4444'};
    padding:12px 20px;border-radius:10px;font-size:14px;
    font-family:'JetBrains Mono',monospace;
    box-shadow:0 8px 24px rgba(0,0,0,.4);
    transition:opacity .3s;
  `;
  document.body.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, 2800);
}

/* ── Bot actions ──────────────────────────────────── */
async function botAction(id, action) {
  const btn = event.currentTarget;
  const orig = btn.textContent;
  btn.disabled = true;
  btn.textContent = '...';
  try {
    const r = await fetch(`/bot/${id}/${action}`, { method: 'POST' });
    const d = await r.json();
    toast(d.message || d.error || 'Done', d.ok !== false);
    setTimeout(() => location.reload(), 900);
  } catch {
    toast('Request failed', false);
    btn.disabled = false;
    btn.textContent = orig;
  }
}

async function deleteBot(id) {
  if (!confirm('Delete this bot and all its files? This cannot be undone.')) return;
  try {
    const r = await fetch(`/bot/${id}/delete`, { method: 'POST' });
    const d = await r.json();
    if (d.ok) { toast('Bot deleted'); setTimeout(() => location.href = '/dashboard', 900); }
    else toast(d.error || 'Delete failed', false);
  } catch {
    toast('Request failed', false);
  }
}

/* ── Auto-scroll logs ─────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  const log = document.querySelector('.log-body');
  if (log) log.scrollTop = log.scrollHeight;
});
