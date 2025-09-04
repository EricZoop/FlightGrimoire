import { parseUbxFile } from './parser.js';

// --- DOM Elements ---
const uploadArea = document.getElementById('upload-area');
const fileInput = document.getElementById('file-input');
const historyList = document.getElementById('history-list');

// --- UI Helper Functions ---
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function downloadCsv(csvContent, filename) {
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', filename);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url); // Clean up the object URL
}

// --- New Save Picker Function ---
async function saveFileWithPicker(csvContent, filename) {
    try {
        const opts = {
            suggestedName: filename,
            types: [
                {
                    description: 'CSV Files',
                    accept: { 'text/csv': ['.csv'] },
                },
            ],
        };
        const handle = await window.showSaveFilePicker(opts);
        const writable = await handle.createWritable();
        await writable.write(csvContent);
        await writable.close();
    } catch (err) {
        console.error('Save cancelled or failed:', err);
    }
}

function showFile(file, result) {
    const now = new Date();
    const timeString = now.toLocaleString();

    const emptyState = historyList.querySelector('.empty-state');
    if (emptyState) {
        emptyState.remove();
    }

    const item = document.createElement('div');
    item.classList.add('history-item');

    if (result.success) {
        item.innerHTML = `
            <div class="file-name">${file.name}</div>
            <div class="file-details">
                <span>${formatFileSize(file.size)}</span>
                <span>${timeString}</span>
            </div>
            <a href="#" class="download-link">${result.filename}</a>
        `;
        const downloadLink = item.querySelector('.download-link');
        if (downloadLink) {
            downloadLink.addEventListener('click', async (e) => {
                e.preventDefault();
                if (window.showSaveFilePicker) {
                    await saveFileWithPicker(result.csvContent, result.filename);
                } else {
                    // fallback for unsupported browsers
                    downloadCsv(result.csvContent, result.filename);
                }
            });
        }
    } else {
        item.innerHTML = `
            <div class="file-name">${file.name}</div>
            <div class="file-details">
                <span>${formatFileSize(file.size)}</span>
                <span>${timeString}</span>
            </div>
            <div class="download-name" style="color: red;">Error: ${result.error}</div>
        `;
    }

    historyList.prepend(item);
}

// --- Main File Handler ---
async function handleFiles(fileList) {
    if (fileList.length === 0) {
        return;
    }
    await Promise.all(
        Array.from(fileList).map(async (file) => {
            const result = await parseUbxFile(file); // Use the imported parser
            showFile(file, result);
        })
    );
}

// --- Event Handlers ---
fileInput.addEventListener('change', (e) => {
    handleFiles(e.target.files);
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
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        fileInput.files = files;
        handleFiles(files);
    }
});
