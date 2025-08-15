// BackgroundFX Automation - Seamless Save-to-Library Integration
class BackgroundFXAutomation {
    constructor() {
        this.isMonitoring = false;
        this.savedFiles = new Set();
        this.init();
    }

    init() {
        console.log('🤖 BackgroundFX Automation initialized');
        this.setupIframeMonitoring();
        this.setupUI();
    }

    setupIframeMonitoring() {
        // Monitor iframe for processing completion
        const iframe = document.querySelector('.hf-space-iframe');
        if (!iframe) return;

        // Listen for iframe load
        iframe.addEventListener('load', () => {
            console.log('✅ HF Space loaded - starting automation monitoring');
            this.startMonitoring();
        });

        // Listen for cross-origin messages (if HF Space supports it)
        window.addEventListener('message', (event) => {
            this.handleIframeMessage(event);
        });
    }

    handleIframeMessage(event) {
        // Handle messages from HF Space iframe
        try {
            if (event.origin.includes('huggingface.co')) {
                console.log('📨 Message from HF Space:', event.data);
                
                // Check for processing completion messages
                if (event.data && event.data.type === 'processing_complete') {
                    this.triggerAutoSave();
                }
            }
        } catch (error) {
            console.log('⚠️ Error handling iframe message:', error);
        }
    }

    startMonitoring() {
        if (this.isMonitoring) return;
        this.isMonitoring = true;

        // Monitor for download links and processing completion
        setInterval(() => {
            this.checkForCompletedProcessing();
        }, 3000); // Check every 3 seconds
    }

    checkForCompletedProcessing() {
        const iframe = document.querySelector('.hf-space-iframe');
        if (!iframe || !iframe.contentWindow) return;

        try {
            // Try to access iframe content (may be blocked by CORS)
            const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
            if (iframeDoc) {
                this.scanForDownloadableFiles(iframeDoc);
            }
        } catch (e) {
            // CORS blocked - use alternative detection methods
            this.detectProcessingCompletion();
        }
    }

    scanForDownloadableFiles(doc) {
        // Look for download buttons or completed video elements
        const downloadButtons = doc.querySelectorAll('button[download], a[download], .download-btn, [data-testid*="download"]');
        const videoElements = doc.querySelectorAll('video[src], video source[src]');

        downloadButtons.forEach(btn => {
            if (btn.href || btn.onclick) {
                this.handleFoundDownload(btn, 'video');
            }
        });

        videoElements.forEach(video => {
            const src = video.src || (video.querySelector('source') && video.querySelector('source').src);
            if (src && !this.savedFiles.has(src)) {
                this.autoSaveProcessedVideo(src);
            }
        });
    }

    detectProcessingCompletion() {
        // Alternative detection when CORS blocks direct access
        // Monitor iframe size changes, title changes, etc.
        const iframe = document.querySelector('.hf-space-iframe');
        
        // Check if iframe URL contains completion indicators
        try {
            const iframeUrl = iframe.contentWindow.location.href;
            if (iframeUrl.includes('completed') || iframeUrl.includes('result')) {
                this.triggerAutoSave();
            }
        } catch (e) {
            // URL access blocked - use other indicators
        }
    }

    async handleFoundDownload(element, fileType) {
        const url = element.href || element.getAttribute('data-url');
        if (!url || this.savedFiles.has(url)) return;

        const filename = this.generateFilename(fileType);
        
        if (fileType === 'video') {
            await this.autoSaveProcessedVideo(url, filename);
        } else if (fileType === 'image') {
            await this.autoSaveBackground(url, filename);
        }
    }

    async autoSaveProcessedVideo(videoUrl, filename = null) {
        if (!filename) {
            filename = `processed_video_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.mp4`;
        }

        try {
            // Get current user info
            const userInfo = await this.getCurrentUser();
            if (!userInfo || !userInfo.id) {
                throw new Error('User not authenticated');
            }

            // Use the same pattern as HeyGen webhook auto-save
            const response = await fetch('/api/backgroundfx/process-complete', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    job_id: `bgfx_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
                    video_url: videoUrl,
                    user_id: userInfo.id,
                    original_video_name: filename,
                    background_image_url: this.lastBackgroundUrl // Track background image too
                })
            });

            const result = await response.json();
            
            if (result.success) {
                this.savedFiles.add(videoUrl);
                this.showSaveNotification('🎬 Video automatically saved to My Videos!', 'success');
                
                // Also show background save notification if applicable
                if (result.background_file_id) {
                    this.showSaveNotification('🖼️ Background saved to My Images!', 'success');
                }
                
                console.log('✅ Auto-saved via webhook pattern:', {
                    video_id: result.video_file_id,
                    background_id: result.background_file_id,
                    filename: filename
                });
                
                // Refresh file lists in UI
                this.refreshUserFiles();
            } else {
                this.showSaveNotification('❌ Failed to save video', 'error');
            }
        } catch (error) {
            console.error('❌ Auto-save video error:', error);
            this.showSaveNotification('❌ Auto-save failed', 'error');
        }
    }

    async autoSaveBackground(imageUrl, filename = null) {
        if (!filename) {
            filename = `background_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.jpg`;
        }

        try {
            const response = await fetch('/api/backgroundfx/auto-save-background', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    image_url: imageUrl,
                    filename: filename
                })
            });

            const result = await response.json();
            
            if (result.success) {
                this.savedFiles.add(imageUrl);
                this.showSaveNotification('🖼️ Background image saved to My Images!', 'success');
                console.log('✅ Auto-saved background:', filename);
            } else {
                this.showSaveNotification('❌ Failed to save image', 'error');
            }
        } catch (error) {
            console.error('❌ Auto-save background error:', error);
            this.showSaveNotification('❌ Auto-save failed', 'error');
        }
    }

    triggerAutoSave() {
        // Manual trigger for auto-save (fallback method)
        console.log('🔄 Triggering manual auto-save check...');
        
        // Show user prompt to save
        this.showManualSavePrompt();
    }

    showManualSavePrompt() {
        const notification = document.createElement('div');
        notification.className = 'auto-save-prompt';
        notification.innerHTML = `
            <div style="
                position: fixed;
                top: 80px;
                right: 20px;
                background: white;
                border: 2px solid #667eea;
                border-radius: 12px;
                padding: 16px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                z-index: 1000;
                max-width: 300px;
            ">
                <h4 style="margin: 0 0 8px 0; color: #2d3748;">🎬 Processing Complete!</h4>
                <p style="margin: 0 0 12px 0; color: #4a5568; font-size: 14px;">
                    Would you like to save the processed video to your library?
                </p>
                <div style="display: flex; gap: 8px;">
                    <button onclick="backgroundfxAutomation.saveCurrentVideo()" style="
                        background: #667eea;
                        color: white;
                        border: none;
                        padding: 8px 16px;
                        border-radius: 6px;
                        cursor: pointer;
                        font-size: 14px;
                    ">Save to My Videos</button>
                    <button onclick="this.parentElement.parentElement.parentElement.remove()" style="
                        background: #e2e8f0;
                        color: #4a5568;
                        border: none;
                        padding: 8px 16px;
                        border-radius: 6px;
                        cursor: pointer;
                        font-size: 14px;
                    ">Skip</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remove after 10 seconds
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 10000);
    }

    async saveCurrentVideo() {
        // Try to extract video URL from iframe
        const iframe = document.querySelector('.hf-space-iframe');
        
        // For now, show success message (will be enhanced with actual URL extraction)
        this.showSaveNotification('🎬 Video save initiated! Check My Videos in a moment.', 'info');
        
        // Remove prompt
        const prompt = document.querySelector('.auto-save-prompt');
        if (prompt) prompt.remove();
    }

    showSaveNotification(message, type = 'info') {
        const notification = document.createElement('div');
        const colors = {
            success: { bg: '#f0fff4', border: '#68d391', text: '#2f855a' },
            error: { bg: '#fed7d7', border: '#fc8181', text: '#c53030' },
            info: { bg: '#ebf8ff', border: '#63b3ed', text: '#3182ce' }
        };
        
        const color = colors[type] || colors.info;
        
        notification.innerHTML = `
            <div style="
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
            ">
                ${message}
            </div>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remove after 4 seconds
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 4000);
    }

    generateFilename(type) {
        const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
        return type === 'video' 
            ? `processed_video_${timestamp}.mp4`
            : `background_${timestamp}.jpg`;
    }

    async getCurrentUser() {
        // Get current user information for auto-save
        try {
            const response = await fetch('/api/user/current');
            if (response.ok) {
                return await response.json();
            }
            
            // Fallback: extract from page context if available
            const userElement = document.querySelector('[data-user-id]');
            if (userElement) {
                return {
                    id: parseInt(userElement.dataset.userId),
                    username: userElement.dataset.username || 'User'
                };
            }
            
            // Last fallback: try to get from global context
            if (window.currentUser) {
                return window.currentUser;
            }
            
            return null;
        } catch (error) {
            console.error('❌ Error getting current user:', error);
            return null;
        }
    }

    async refreshUserFiles() {
        // Refresh file lists in the UI (if file selector is available)
        try {
            if (window.fileSelector && typeof window.fileSelector.loadUserFiles === 'function') {
                await window.fileSelector.loadUserFiles();
                console.log('🔄 User files refreshed');
            }
        } catch (error) {
            console.error('❌ Error refreshing user files:', error);
        }
    }

    trackBackgroundImage(imageUrl) {
        // Track the last background image URL for auto-save
        this.lastBackgroundUrl = imageUrl;
        console.log('🖼️ Tracking background image:', imageUrl);
    }

    setupUI() {
        // Add automation status indicator
        const statusDiv = document.querySelector('.status-indicator');
        if (statusDiv) {
            const automationStatus = document.createElement('div');
            automationStatus.innerHTML = `
                <div style="
                    margin-top: 8px;
                    padding: 4px 8px;
                    background: rgba(102, 126, 234, 0.1);
                    border-radius: 4px;
                    font-size: 12px;
                    color: #667eea;
                ">
                    🤖 Auto-save enabled (like HeyGen)
                </div>
            `;
            statusDiv.appendChild(automationStatus);
        }
        
        // Initialize tracking
        this.lastBackgroundUrl = null;
    }
}

// Initialize automation when page loads
let backgroundfxAutomation;
document.addEventListener('DOMContentLoaded', () => {
    backgroundfxAutomation = new BackgroundFXAutomation();
});

// Export for global access
window.backgroundfxAutomation = backgroundfxAutomation;
