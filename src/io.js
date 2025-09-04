const uploadArea = document.getElementById('upload-area');
const fileInput = document.getElementById('file-input');
const preview = document.getElementById('preview');
const historyList = document.getElementById('history-list');

function showFile(file) {
    const time = new Date().toLocaleTimeString();

    // Update preview
    preview.innerHTML = `
    <div class="file-info">
        <strong>${file.name}</strong><br>
        <span>${(file.size / 1024).toFixed(2)} KB</span>
        <div class="timestamp">Processed at: ${time}</div>
    </div>
    `;

    // Add to history
    const item = document.createElement('div');
    item.classList.add('history-item');
    item.innerHTML = `<strong>${file.name}</strong><span>${time}</span>`;
    historyList.prepend(item);
}

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
    showFile(e.target.files[0]);
    }
});

uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('dragover');
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('dragover');
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    if (e.dataTransfer.files.length > 0) {
    fileInput.files = e.dataTransfer.files;
    showFile(e.dataTransfer.files[0]);
    }
});