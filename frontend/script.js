const form = document.querySelector('#verify-form');
const verifyButton = document.querySelector('#verify-button');
const formMessage = document.querySelector('#form-message');
const result = document.querySelector('#result');
const downloadButton = document.querySelector('#download-button');
const eventSelect = document.querySelector('#event');
const apiBaseUrl = 'https://certificate-api-w6r6.onrender.com';

async function fetchWithRetry(url, options = {}, attempts = 2) {
    let lastError;
    for (let attempt = 0; attempt < attempts; attempt += 1) {
        try {
            const response = await fetch(url, options);
            if (response.ok || attempt === attempts - 1) return response;
        } catch (error) {
            lastError = error;
            if (attempt === attempts - 1) throw error;
        }
        await new Promise((resolve) => setTimeout(resolve, 1500));
    }
    throw lastError || new Error('The certificate service is unavailable.');
}

let verifiedEmail = '';
let verifiedEvent = '';

async function loadEvents() {
    try {
        const response = await fetchWithRetry(`${apiBaseUrl}/events`);
        const events = await response.json();
        if (!response.ok || !events.length) {
            throw new Error('No events are available yet.');
        }

        eventSelect.replaceChildren(new Option('Select an event', ''));
        events.forEach((eventName) => eventSelect.add(new Option(eventName, eventName)));
        eventSelect.disabled = false;
    } catch (error) {
        eventSelect.replaceChildren(new Option(error.message, ''));
        const message = error instanceof TypeError
            ? 'Unable to connect to the certificate service. Check the deployed API URL and CORS settings.'
            : error.message;
        showMessage(message, 'error');
    }
}

loadEvents();

function showMessage(message, type = '') {
    formMessage.textContent = message;
    formMessage.className = `form-message ${type}`;
}

function setResult(data) {
    document.querySelector('#result-name').textContent = data.name || '-';
    document.querySelector('#result-course').textContent = data.course || '-';
    document.querySelector('#result-rank').textContent = data.rank || 'Participant';
    document.querySelector('#result-message').textContent = data.message;
    result.hidden = false;
}

function clearResult() {
    result.hidden = true;
    verifiedEmail = '';
    verifiedEvent = '';
}

form.addEventListener('submit', async (event) => {
    event.preventDefault();
    clearResult();

    const formData = new FormData(form);
    const email = formData.get('email').trim();
    const eventName = formData.get('event').trim();

    for (const field of form.querySelectorAll('input, select')) {
        field.classList.toggle('invalid', !field.value.trim() || (field.type === 'email' && !field.validity.valid));
    }

    if (!email || !eventName || !form.querySelector('#email').validity.valid) {
        showMessage('Please enter a valid email address and select an event.', 'error');
        return;
    }

    verifyButton.disabled = true;
    verifyButton.classList.add('is-loading');
    verifyButton.querySelector('span:first-child').textContent = 'Checking registration...';
    showMessage('');

    try {
        const response = await fetchWithRetry(`${apiBaseUrl}/certificate/verify`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, event: eventName }),
        });
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'The verification service is unavailable.');
        }

        if (!data.eligible) {
            showMessage(data.message, 'error');
            return;
        }

        verifiedEmail = email;
        verifiedEvent = eventName;
        setResult(data);
        showMessage('Your registration details match our records.', 'success');
    } catch (error) {
        showMessage(error.message || 'Unable to verify right now. Please try again.', 'error');
    } finally {
        verifyButton.disabled = false;
        verifyButton.classList.remove('is-loading');
        verifyButton.querySelector('span:first-child').textContent = 'Verify registration';
    }
});

downloadButton.addEventListener('click', async () => {
    if (!verifiedEmail || !verifiedEvent) return;

    downloadButton.disabled = true;
    downloadButton.classList.add('is-loading');
    downloadButton.querySelector('span:last-child').textContent = 'Preparing certificate...';

    try {
        const url = `${apiBaseUrl}/certificate/download/${encodeURIComponent(verifiedEmail)}/${encodeURIComponent(verifiedEvent)}`;
        const response = await fetchWithRetry(url);
        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.detail || 'Certificate could not be downloaded.');
        }

        const blob = await response.blob();
        const downloadUrl = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = 'certificate.pdf';
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(downloadUrl), 1000);
    } catch (error) {
        showMessage(error.message || 'Unable to download the certificate.', 'error');
    } finally {
        downloadButton.disabled = false;
        downloadButton.classList.remove('is-loading');
        downloadButton.querySelector('span:last-child').textContent = 'Download certificate';
    }
});
