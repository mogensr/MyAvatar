/**
 * Text-to-Video functionality for MyAvatar
 * Handles the UI toggle between audio recording and text input modes
 * and submits text-to-video generation requests
 */
document.addEventListener('DOMContentLoaded', function() {
    // Get UI elements
    const inputTypeSelector = document.getElementById('input-type-selector');
    const audioRecordingSection = document.getElementById('audio-recording-section');
    const textInputSection = document.getElementById('text-input-section');
    const textToVideoForm = document.getElementById('text-to-video-form');
    const submitTextBtn = document.getElementById('submit-text-btn');
    const scriptTextarea = document.getElementById('script-textarea');
    const voiceSelector = document.getElementById('voice-selector');

    // Toggle between audio recording and text input
    if (inputTypeSelector) {
        inputTypeSelector.addEventListener('change', function() {
            const selectedValue = this.value;
            if (selectedValue === 'audio') {
                audioRecordingSection.style.display = 'block';
                textInputSection.style.display = 'none';
            } else if (selectedValue === 'text') {
                audioRecordingSection.style.display = 'none';
                textInputSection.style.display = 'block';
            }
        });
    }

    // Handle text-to-video form submission
    if (textToVideoForm) {
        textToVideoForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Validate form
            if (!scriptTextarea.value.trim()) {
                alert('Please enter a script for your video');
                return;
            }
            
            // Disable button to prevent multiple submissions
            submitTextBtn.disabled = true;
            submitTextBtn.innerHTML = 'Generating Video...';
            
            // Get form data
            const formData = new FormData(textToVideoForm);
            
            // Get avatar_id from the form or from another element on the page
            const avatarId = document.getElementById('avatar-id').value;
            formData.append('avatar_id', avatarId);
            
            // Submit the form
            fetch('/api/heygen/text', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Success - show message and reload or update UI
                    showNotification('Video generation started! It will appear in your videos soon.', 'success');
                    
                    // Reset form
                    scriptTextarea.value = '';
                    
                    // Optional: Redirect to video status page
                    // window.location.href = '/videos';
                } else {
                    // Error
                    showNotification('Error: ' + (data.error || 'Failed to generate video'), 'error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('An error occurred. Please try again.', 'error');
            })
            .finally(() => {
                // Re-enable button
                submitTextBtn.disabled = false;
                submitTextBtn.innerHTML = 'Generate Video';
            });
        });
    }

    // Helper function to show notifications
    function showNotification(message, type) {
        // You can implement this based on your UI notification system
        // For example:
        const notificationArea = document.getElementById('notification-area');
        if (notificationArea) {
            const notification = document.createElement('div');
            notification.className = `notification ${type}`;
            notification.textContent = message;
            notificationArea.appendChild(notification);
            
            // Auto-remove after 5 seconds
            setTimeout(() => {
                notificationArea.removeChild(notification);
            }, 5000);
        } else {
            // Fallback to alert if no notification area exists
            alert(message);
        }
    }
});
