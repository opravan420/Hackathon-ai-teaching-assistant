/**
 * Global Shared File Upload Handler
 * Automatically handles visual file-selection state, file info formatting,
 * drag-and-drop, validation, Change File, and Remove for any .js-file-upload-container.
 */
document.addEventListener('DOMContentLoaded', function() {
    function formatBytes(bytes) {
        if (!bytes || bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    function initFileUploadContainer(container) {
        const fileInput = container.querySelector('.js-file-input');
        const emptyState = container.querySelector('.js-empty-state');
        const selectedState = container.querySelector('.js-selected-state');
        const filenameEl = container.querySelector('.js-filename');
        const filesizeEl = container.querySelector('.js-filesize');
        const errorEl = container.parentElement ? container.parentElement.querySelector('.js-error-msg') : null;
        const btnChange = container.querySelector('.js-btn-change');
        const btnRemove = container.querySelector('.js-btn-remove');

        if (!fileInput) return;

        const maxMb = parseFloat(container.dataset.maxSizeMb || 10);
        const maxSizeBytes = maxMb * 1024 * 1024;
        const acceptAttr = container.dataset.acceptTypes || fileInput.getAttribute('accept') || '';
        
        let allowedExtensions = [];
        if (acceptAttr) {
            allowedExtensions = acceptAttr.split(',')
                .map(item => item.trim().toLowerCase().replace('.', ''))
                .filter(item => item.length > 0 && !item.includes('/'));
        }

        function resetToEmptyState() {
            fileInput.value = '';
            if (emptyState) emptyState.classList.remove('hidden');
            if (selectedState) selectedState.classList.add('hidden');
            if (errorEl) {
                errorEl.textContent = '';
                errorEl.classList.add('hidden');
            }
            fileInput.style.pointerEvents = 'auto';
        }

        function handleFile(file) {
            if (!file) return;

            const ext = file.name.split('.').pop().toLowerCase();
            
            if (allowedExtensions.length > 0 && !allowedExtensions.includes(ext)) {
                if (errorEl) {
                    errorEl.textContent = `Invalid file type. Allowed formats: ${allowedExtensions.map(e => '.' + e.toUpperCase()).join(', ')}.`;
                    errorEl.classList.remove('hidden');
                }
                resetToEmptyState();
                return;
            }

            if (file.size > maxSizeBytes) {
                if (errorEl) {
                    errorEl.textContent = `File is too large. Maximum file size is ${maxMb}MB.`;
                    errorEl.classList.remove('hidden');
                }
                resetToEmptyState();
                return;
            }

            if (errorEl) {
                errorEl.textContent = '';
                errorEl.classList.add('hidden');
            }

            if (filenameEl) filenameEl.textContent = file.name;
            if (filesizeEl) filesizeEl.textContent = formatBytes(file.size);

            if (emptyState) emptyState.classList.add('hidden');
            if (selectedState) selectedState.classList.remove('hidden');
            fileInput.style.pointerEvents = 'none';
        }

        fileInput.addEventListener('change', function() {
            if (this.files && this.files[0]) {
                handleFile(this.files[0]);
            }
        });

        if (btnChange) {
            btnChange.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                fileInput.style.pointerEvents = 'auto';
                fileInput.click();
            });
        }

        if (btnRemove) {
            btnRemove.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                resetToEmptyState();
            });
        }

        // Drag & Drop handlers
        ['dragenter', 'dragover'].forEach(eventName => {
            container.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                container.classList.add('border-indigo-500', 'bg-indigo-50/50');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            container.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                container.classList.remove('border-indigo-500', 'bg-indigo-50/50');
            }, false);
        });

        container.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt ? dt.files : null;
            if (files && files.length > 0) {
                try {
                    const dataTransfer = new DataTransfer();
                    for (let i = 0; i < files.length; i++) {
                        dataTransfer.items.add(files[i]);
                    }
                    fileInput.files = dataTransfer.files;
                } catch (err) {
                    try {
                        fileInput.files = files;
                    } catch (err2) {}
                }
                handleFile(files[0]);
            }
        }, false);
    }

    // Initialize all file upload containers on the page
    document.querySelectorAll('.js-file-upload-container').forEach(initFileUploadContainer);
});
