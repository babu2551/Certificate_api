const form = document.querySelector('#verify-form');
const verifyButton = document.querySelector('#verify-button');
const formMessage = document.querySelector('#form-message');
const result = document.querySelector('#result');
const downloadButton = document.querySelector('#download-button');
const eventSelect = document.querySelector('#event');
const apiBaseUrl = ['5500', '5501'].includes(window.location.port)
    ? 'https://certificate-api-w6r6.onrender.com'
    : '';

let verifiedEmail = '';
let verifiedEvent = '';

async function loadEvents() {
    try {
        const response = await fetch(`${apiBaseUrl}/events`);
        const events = await response.json();
        if (!response.ok || !events.length) {
            throw new Error('No events are available yet.');
        }

        eventSelect.replaceChildren(new Option('Select an event', ''));
        events.forEach((eventName) => eventSelect.add(new Option(eventName, eventName)));
        eventSelect.disabled = false;
    } catch (error) {
        eventSelect.replaceChildren(new Option(error.message, ''));
        showMessage(`${error.message} Start the FastAPI server and refresh the page.`, 'error');
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
    verifyButton.querySelector('span:first-child').textContent = 'Checking registration...';
    showMessage('');

    try {
        const response = await fetch(`${apiBaseUrl}/certificate/verify`, {
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
        verifyButton.querySelector('span:first-child').textContent = 'Verify registration';
    }
});

downloadButton.addEventListener('click', async () => {
    if (!verifiedEmail || !verifiedEvent) return;

    downloadButton.disabled = true;
    downloadButton.querySelector('span:last-child').textContent = 'Preparing certificate...';

    try {
        const url = `${apiBaseUrl}/certificate/download/${encodeURIComponent(verifiedEmail)}/${encodeURIComponent(verifiedEvent)}`;
        const response = await fetch(url);
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
        URL.revokeObjectURL(downloadUrl);
    } catch (error) {
        showMessage(error.message || 'Unable to download the certificate.', 'error');
    } finally {
        downloadButton.disabled = false;
        downloadButton.querySelector('span:last-child').textContent = 'Download certificate';
    }
});
