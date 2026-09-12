const isDashboardPage = document.body.dataset.page === 'dashboard';
const apiBaseUrl = 'https://certificate-api-w6r6.onrender.com';
const message = document.querySelector('#admin-message');
const loginScreen = document.querySelector('#login-screen');
const dashboardContent = document.querySelector('#dashboard-content');
const loginForm = document.querySelector('#login-form');
const loginError = document.querySelector('#login-error');
const loginButton = loginForm?.querySelector('button[type="submit"]');
const dashboardLoader = document.querySelector('#dashboard-loader');
const authStorageKey = 'certificate-admin-authorization';
let adminAuthorization = sessionStorage.getItem(authStorageKey) || '';

function showMessage(text, type = '') {
    message.textContent = text;
    message.className = `admin-message ${type}`;
}

function setDashboardLoading(isLoading) {
    dashboardLoader?.classList.toggle('is-visible', isLoading);
    document.body.classList.toggle('is-loading', isLoading);
}

async function request(path, options = {}) {
    const headers = new Headers(options.headers || {});
    if (adminAuthorization) headers.set('Authorization', adminAuthorization);
    let response;
    try {
        response = await fetch(`${apiBaseUrl}${path}`, { ...options, headers });
    } catch (error) {
        throw new Error(`Cannot reach the certificate API at ${apiBaseUrl}.`);
    }
    const data = await response.json().catch(() => ({}));
    if (response.status === 401) throw new Error('Your admin ID or password is incorrect.');
    if (!response.ok) throw new Error(data.detail || 'The admin service is unavailable.');
    return data;
}

function formatDate(value) {
    if (!value) return '—';
    return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(value));
}

function renderEvents(events) {
    const list = document.querySelector('#events-list');
    if (!events.length) { list.innerHTML = '<p class="empty-state">No events yet. Create one to get started.</p>'; return; }
    list.innerHTML = events.slice(0, 6).map((event) => `<div class="event-row"><span class="event-icon">✦</span><div><strong>${escapeHtml(event.name)}</strong><small>${event.date ? formatDate(event.date) : 'Date not set'}${event.description ? ` · ${escapeHtml(event.description)}` : ''}</small></div><button class="delete-button delete-event" data-event="${escapeHtml(event.name)}" title="Delete event" type="button" aria-label="Delete ${escapeHtml(event.name)}">×</button></div>`).join('');
}

function renderRegistrations(rows) {
    const body = document.querySelector('#registrations-body');
    if (!rows.length) { body.innerHTML = '<tr><td colspan="6" class="empty-state">No registrations yet.</td></tr>'; return; }
    body.innerHTML = rows.map((row) => `<tr><td><strong>${escapeHtml(row.name)}</strong><small>${escapeHtml(row.email)}</small></td><td>${escapeHtml(row.event)}</td><td>${escapeHtml(row.course)}</td><td>${formatDate(row.created_at)}</td><td><span class="status ${row.downloaded_at ? 'downloaded' : 'pending'}"><i></i>${row.downloaded_at ? 'Downloaded' : 'Not downloaded'}</span></td><td><button class="delete-button delete-student" data-email="${escapeHtml(row.email)}" data-event="${escapeHtml(row.event)}" title="Delete student" type="button" aria-label="Delete ${escapeHtml(row.name)}">×</button></td></tr>`).join('');
}

function escapeHtml(value = '') { const node = document.createElement('span'); node.textContent = value; return node.innerHTML; }

async function loadDashboard() {
    setDashboardLoading(true);
    try {
        const data = await request('/admin/dashboard');
        const { stats } = data;
        document.querySelector('#stat-students').textContent = stats.students;
        document.querySelector('#stat-downloaded').textContent = stats.downloaded;
        document.querySelector('#stat-pending').textContent = stats.pending;
        document.querySelector('#stat-events').textContent = stats.events;
        document.querySelector('#download-rate').textContent = `${stats.students ? Math.round(stats.downloaded / stats.students * 100) : 0}% of all students`;
        renderEvents(data.events);
        renderRegistrations(data.recent_registrations);
        showMessage(`Last synced ${new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' }).format(new Date())}`, 'success');
    } catch (error) { showMessage(error.message, 'error'); }
    finally { setDashboardLoading(false); }
}

async function signIn(event) {
    event.preventDefault();
    const formData = new FormData(loginForm);
    const username = formData.get('username').trim();
    const password = formData.get('password');
    adminAuthorization = `Basic ${btoa(`${username}:${password}`)}`;
    loginError.textContent = '';
    loginButton?.classList.add('is-loading');
    if (loginButton) loginButton.disabled = true;
    try {
        await request('/admin/dashboard');
        sessionStorage.setItem(authStorageKey, adminAuthorization);
        const dashboardUrl = window.location.href.split('?')[0].replace(/admin\.html$/, 'dashboard.html');
        window.location.assign(dashboardUrl);
    } catch (error) {
        adminAuthorization = '';
        sessionStorage.removeItem(authStorageKey);
        loginError.textContent = error.message;
    } finally {
        loginButton?.classList.remove('is-loading');
        if (loginButton) loginButton.disabled = false;
    }
}

async function openSavedDashboard() {
    if (!isDashboardPage) return;
    if (!adminAuthorization) {
        window.location.href = 'admin.html';
        return;
    }
    try {
        await request('/admin/dashboard');
        await loadDashboard();
    } catch (error) {
        adminAuthorization = '';
        sessionStorage.removeItem(authStorageKey);
        window.location.href = 'admin.html';
    }
}

if (loginForm) loginForm.addEventListener('submit', signIn);

if (isDashboardPage) {
    document.querySelector('#refresh-button').addEventListener('click', loadDashboard);
    document.querySelector('#csv-file').addEventListener('change', (event) => { document.querySelector('#file-name').textContent = event.target.files[0]?.name || 'Choose a CSV file'; });
    document.querySelector('#upload-form').addEventListener('submit', async (event) => {
        event.preventDefault();
        const button = event.target.querySelector('button'); button.disabled = true;
        try { const data = await request('/admin/registrations/upload', { method: 'POST', body: new FormData(event.target) }); showMessage(data.message, 'success'); event.target.reset(); document.querySelector('#file-name').textContent = 'Choose a CSV file'; await loadDashboard(); }
        catch (error) { showMessage(error.message, 'error'); }
        finally { button.disabled = false; }
    });

    document.querySelector('#event-form').addEventListener('submit', async (event) => {
        event.preventDefault();
        try { const data = await request('/admin/events', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(Object.fromEntries(new FormData(event.target))) }); showMessage(data.message, 'success'); event.target.closest('dialog').close(); event.target.reset(); await loadDashboard(); }
        catch (error) { showMessage(error.message, 'error'); }
    });

    document.querySelector('#certificate-form').addEventListener('submit', async (event) => {
        event.preventDefault();
        try { const data = await request('/admin/certificates', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(Object.fromEntries(new FormData(event.target))) }); showMessage(data.message, 'success'); event.target.closest('dialog').close(); event.target.reset(); await loadDashboard(); }
        catch (error) { showMessage(error.message, 'error'); }
    });

    document.querySelectorAll('[data-open]').forEach((button) => button.addEventListener('click', () => document.querySelector(`#${button.dataset.open}`).showModal()));

    document.querySelector('#events-list').addEventListener('click', async (event) => {
        const button = event.target.closest('.delete-event');
        if (!button || !window.confirm(`Delete event "${button.dataset.event}" and all related student records?`)) return;
        try {
            const data = await request(`/admin/events/${encodeURIComponent(button.dataset.event)}`, { method: 'DELETE' });
            showMessage(data.message, 'success');
            await loadDashboard();
        } catch (error) { showMessage(error.message, 'error'); }
    });

    document.querySelector('#registrations-body').addEventListener('click', async (event) => {
        const button = event.target.closest('.delete-student');
        if (!button || !window.confirm(`Delete ${button.dataset.email}'s registration and certificate?`)) return;
        try {
            const path = `/admin/registrations/${encodeURIComponent(button.dataset.email)}/${encodeURIComponent(button.dataset.event)}`;
            const data = await request(path, { method: 'DELETE' });
            showMessage(data.message, 'success');
            await loadDashboard();
        } catch (error) { showMessage(error.message, 'error'); }
    });
}

openSavedDashboard();
