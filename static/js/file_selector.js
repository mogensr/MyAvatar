// Clean File Selector for BackgroundFX
class FileSelector {
    constructor() {
        this.selectedVideo = null;
        this.selectedBackground = null;
        this.userFiles = { videos: [], images: [] };
        this.init();
    }

    init() {
        console.log('🎯 File Selector initialized');
        this.setupFileInputs();
        this.loadUserFiles();
    }

    setupFileInputs() {
        // Setup direct file upload inputs
        const videoInput = document.getElementById('video-file-input');
        const imageInput = document.getElementById('image-file-input');

        if (videoInput) {
            videoInput.addEventListener('change', (e) => {
                if (e.target.files.length > 0) {
                    this.handleDirectUpload(e.target.files[0], 'video');
                }
            });
        }

        if (imageInput) {
            imageInput.addEventListener('change', (e) => {
                if (e.target.files.length > 0) {
                    this.handleDirectUpload(e.target.files[0], 'image');
                }
            });
        }
    }

    async loadUserFiles() {
        try {
            // Load user's videos
            const videoResponse = await fetch('/api/backgroundfx/my-videos');
            if (videoResponse.ok) {
                const videoData = await videoResponse.json();
                this.userFiles.videos = videoData.files || [];
            }

            // Load user's images
            const imageResponse = await fetch('/api/backgroundfx/my-images');
            if (imageResponse.ok) {
                const imageData = await imageResponse.json();
                this.userFiles.images = imageData.files || [];
            }

            console.log('📁 User files loaded:', this.userFiles);
        } catch (error) {
            console.error('❌ Error loading user files:', error);
        }
    }

    // File Selection Methods
    openVideoSelector() {
        document.getElementById('video-file-input').click();
    }

    openImageSelector() {
        document.getElementById('image-file-input').click();
    }

    openMyVideos() {
        this.showFileModal('video');
    }

    openMyImages() {
        this.showFileModal('image');
    }

    showFileModal(type) {
        const modalId = `${type}-modal`;
        const modal = document.getElementById(modalId);
        const gridId = `${type}-grid-modal`;
        const grid = document.getElementById(gridId);

        if (!modal || !grid) return;

        // Populate modal with user files
        const files = type === 'video' ? this.userFiles.videos : this.userFiles.images;
        this.populateModalGrid(grid, files, type);

        // Show modal
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    populateModalGrid(grid, files, type) {
        if (files.length === 0) {
            grid.innerHTML = `
                <div style="grid-column: 1 / -1; text-align: center; padding: 40px; color: #a0aec0;">
                    <i class="fas fa-${type === 'video' ? 'video' : 'image'}" style="font-size: 2rem; margin-bottom: 12px;"></i>
                    <p>No ${type}s found</p>
                    <p style="font-size: 0.9rem; margin-top: 8px;">Upload some ${type}s first to see them here</p>
                </div>
            `;
            return;
        }

        grid.innerHTML = files.map(file => `
            <div class="file-item-modal" data-file-id="${file.id}" data-file-path="${file.file_path}" data-file-name="${file.filename}">
                <div class="file-preview-modal">
                    <i class="fas fa-${type === 'video' ? 'video' : 'image'}"></i>
                </div>
                <div class="file-name-modal">${file.filename}</div>
            </div>
        `).join('');

        // Add click handlers
        grid.querySelectorAll('.file-item-modal').forEach(item => {
            item.addEventListener('click', () => {
                // Remove previous selection
                grid.querySelectorAll('.file-item-modal').forEach(i => i.classList.remove('selected'));
                // Add selection to clicked item
                item.classList.add('selected');
            });
        });
    }

    selectFromModal(type) {
        const modalId = `${type}-modal`;
        const grid = document.getElementById(`${type}-grid-modal`);
        const selectedItem = grid.querySelector('.file-item-modal.selected');

        if (!selectedItem) {
            alert(`Please select a ${type} first`);
            return;
        }

        const fileData = {
            id: selectedItem.dataset.fileId,
            path: selectedItem.dataset.filePath,
            name: selectedItem.dataset.fileName
        };

        if (type === 'video') {
            this.selectedVideo = fileData;
            this.updateSelectedDisplay('video', fileData.name);
        } else {
            this.selectedBackground = fileData;
            this.updateSelectedDisplay('background', fileData.name);
        }

        this.closeModal(modalId);
        console.log(`✅ Selected ${type}:`, fileData);
    }

    closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('active');
            document.body.style.overflow = '';
        }
    }

    handleDirectUpload(file, type) {
        // Show file as selected
        const fileName = file.name;
        
        if (type === 'video') {
            this.selectedVideo = { file, name: fileName, isUpload: true };
            this.updateSelectedDisplay('video', fileName);
        } else {
            this.selectedBackground = { file, name: fileName, isUpload: true };
            this.updateSelectedDisplay('background', fileName);
        }

        console.log(`📁 Direct upload selected - ${type}:`, fileName);
        
        // Optionally auto-upload to user's library
        this.uploadToLibrary(file, type);
    }

    async uploadToLibrary(file, type) {
        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('file_type', type);

            const response = await fetch('/api/backgroundfx/upload-file', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();
            
            if (result.success) {
                console.log(`✅ File uploaded to library: ${file.name}`);
                // Refresh user files
                this.loadUserFiles();
                
                // Show success notification
                this.showNotification(`📁 ${file.name} saved to My ${type === 'video' ? 'Videos' : 'Images'}!`, 'success');
            } else {
                console.error('❌ Upload failed:', result.message);
            }
        } catch (error) {
            console.error('❌ Upload error:', error);
        }
    }

    updateSelectedDisplay(type, fileName) {
        const displayId = type === 'video' ? 'selected-video' : 'selected-background';
        const display = document.getElementById(displayId);
        
        if (display) {
            display.innerHTML = `
                <span class="file-selected">
                    <i class="fas fa-check-circle"></i>
                    ${fileName}
                </span>
            `;
        }
        
        // INTEGRATION: Also populate the HF Space upload areas
        this.populateHFSpaceUpload(type, fileName);
    }

    populateHFSpaceUpload(type, fileName) {
        // Find the HF Space iframe and try to populate its upload areas
        const iframe = document.querySelector('.hf-space-iframe');
        if (!iframe) return;

        try {
            // Try to access iframe content (may be blocked by CORS)
            const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
            if (iframeDoc) {
                this.directlyPopulateHFSpace(iframeDoc, type, fileName);
            } else {
                // CORS blocked - show user instructions instead
                this.showIntegrationInstructions(type, fileName);
            }
        } catch (e) {
            // CORS blocked - show user instructions
            this.showIntegrationInstructions(type, fileName);
        }
    }

    directlyPopulateHFSpace(iframeDoc, type, fileName) {
        // Try to find and populate HF Space upload areas directly
        const uploadAreas = iframeDoc.querySelectorAll('[data-testid*="upload"], .upload-area, input[type="file"]');
        
        uploadAreas.forEach(area => {
            if (type === 'video' && (area.accept?.includes('video') || area.textContent?.includes('video'))) {
                this.setHFSpaceValue(area, fileName);
            } else if (type === 'image' && (area.accept?.includes('image') || area.textContent?.includes('image'))) {
                this.setHFSpaceValue(area, fileName);
            }
        });
    }

    setHFSpaceValue(element, fileName) {
        // Set the value in HF Space upload element
        if (element.tagName === 'INPUT') {
            // For file inputs, we can't set the value directly, but we can trigger events
            element.dispatchEvent(new Event('change', { bubbles: true }));
        } else {
            // For other elements, update the display text
            const textElement = element.querySelector('.file-name, .filename, [class*="name"]');
            if (textElement) {
                textElement.textContent = fileName;
            }
        }
    }

    showIntegrationInstructions(type, fileName) {
        // Show user-friendly instructions when direct integration isn't possible
        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 120px;
            right: 20px;
            background: #ebf8ff;
            border: 1px solid #63b3ed;
            color: #3182ce;
            padding: 16px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            z-index: 1000;
            font-size: 14px;
            max-width: 350px;
        `;
        
        notification.innerHTML = `
            <div style="display: flex; align-items: flex-start; gap: 8px;">
                <i class="fas fa-info-circle" style="color: #3182ce; margin-top: 2px;"></i>
                <div>
                    <strong>File Selected: ${fileName}</strong><br>
                    <span style="font-size: 13px; opacity: 0.9;">
                        Now upload this ${type} in the "${type === 'video' ? 'Upload Your Video' : 'Upload Background Image'}" section below
                    </span>
                </div>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remove after 6 seconds
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 6000);
        
        // Also highlight the relevant HF Space upload area
        this.highlightHFSpaceUploadArea(type);
    }

    highlightHFSpaceUploadArea(type) {
        // Add visual highlighting to guide user to the correct upload area
        const iframe = document.querySelector('.hf-space-iframe');
        if (!iframe) return;

        // Add a subtle border highlight to the iframe
        iframe.style.border = '3px solid #63b3ed';
        iframe.style.borderRadius = '8px';
        
        // Remove highlight after 5 seconds
        setTimeout(() => {
            iframe.style.border = '';
            iframe.style.borderRadius = '';
        }, 5000);
    }

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        const colors = {
            success: { bg: '#f0fff4', border: '#68d391', text: '#2f855a' },
            error: { bg: '#fed7d7', border: '#fc8181', text: '#c53030' },
            info: { bg: '#ebf8ff', border: '#63b3ed', text: '#3182ce' }
        };
        
        const color = colors[type] || colors.info;
        
        notification.style.cssText = `
            position: fixed;
            top: 80px;
            right: 20px;
            background: ${color.bg};
            border: 1px solid ${color.border};
            color: ${color.text};
            padding: 12px 16px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            z-index: 1000;
            font-size: 14px;
            max-width: 300px;
        `;
        
        notification.textContent = message;
        document.body.appendChild(notification);
        
        // Auto-remove after 4 seconds
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 4000);
    }

    // Get current selections for external use
    getSelections() {
        return {
            video: this.selectedVideo,
            background: this.selectedBackground
        };
    }

    // Reset selections
    reset() {
        this.selectedVideo = null;
        this.selectedBackground = null;
        
        const videoDisplay = document.getElementById('selected-video');
        const backgroundDisplay = document.getElementById('selected-background');
        
        if (videoDisplay) {
            videoDisplay.innerHTML = '<span class="no-selection">No video selected</span>';
        }
        
        if (backgroundDisplay) {
            backgroundDisplay.innerHTML = '<span class="no-selection">No background selected</span>';
        }
    }
}

// Initialize file selector when page loads
let fileSelector;
document.addEventListener('DOMContentLoaded', () => {
    fileSelector = new FileSelector();
});

// Export for global access
window.fileSelector = fileSelector;
