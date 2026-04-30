async function refresh() {
    const btn = document.getElementById('refreshBtn');
    const status = document.getElementById('status');
    btn.disabled = true;
    status.className = 'status';
    status.textContent = 'Scraping... this takes ~30s';

    try {
        const res = await fetch('/refresh', { method: 'POST' });
        const data = await res.json();
        const failed = Object.entries(data).filter(([k, v]) => v !== 'ok');

        if (failed.length === 0) {
            status.className = 'status success';
            status.textContent = 'Done — reloading...';
            setTimeout(() => location.reload(), 800);
        } else {
            status.className = 'status error';
            status.textContent = 'Errors: ' + failed.map(([k, v]) => `${k}: ${v}`).join(' | ');
            btn.disabled = false;
        }
    } catch (e) {
        status.className = 'status error';
        status.textContent = 'Request failed: ' + e.message;
        btn.disabled = false;
    }
}

document.getElementById('refreshBtn').addEventListener('click', refresh);