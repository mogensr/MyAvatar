// Global variables for video monitoring
let videoUpdateInterval = null;
let processingVideos = new Set();

// Initialize user data
document.addEventListener('DOMContentLoaded', function() {
    const username = '{{ username or "User" }}';
    if (username && username !== 'User') {
        document.getElementById('userName').textContent = username;
        document.getElementById('userAvatar').textContent = username.charAt(0).toUpperCase();
    }

    // Initialize video status monitoring
    initVideoStatusMonitoring();
    
    // Initialize avatar carousel
    initAvatarCarousel();
});

// ==================== VIDEO STATUS MONITORING ==================== 
function initVideoStatusMonitoring() {
    console.log('🚀 Initializing video status monitoring...');
    
    // Find all processing/pending videos
    const processingCards = document.querySelectorAll('[data-status="processing"], [data-status="pending"]');
    
    processingCards.forEach(card => {
        const videoId = card.getAttribute('data-video-id');
        if (videoId) {
            processingVideos.add(videoId);
        }
    });

    if (processingVideos.size > 0) {
        console.log(`📹 Found ${processingVideos.size} processing videos: ${Array.from(processingVideos).join(', ')}`);
        startVideoStatusUpdater();
        showStatusIndicator('processing', `Monitoring ${processingVideos.size} video(s)...`);
    } else {
        console.log('✅ No processing videos found');
    }
}

function startVideoStatusUpdater() {
    // Clear existing interval
    if (videoUpdateInterval) {
        clearInterval(videoUpdateInterval);
    }

    // Start checking every 30 seconds
    videoUpdateInterval = setInterval(async () => {
        if (processingVideos.size === 0) {
            console.log('🛑 No more processing videos, stopping monitor');
            clearInterval(videoUpdateInterval);
            hideStatusIndicator();
            return;
        }

        console.log(`🔍 Checking ${processingVideos.size} processing videos...`);
        
        for (const videoId of processingVideos) {
            await checkVideoStatus(videoId, false); // false = auto-check, not manual
        }
    }, 30000); // 30 seconds
}

async function checkVideoStatus(videoId, isManual = true) {
    try {
        console.log(`🎬 Checking video ${videoId}...`);

        const response = await fetch(`/api/debug-video-status/${videoId}`);
        
        if (response.ok) {
            const data = await response.json();
            
            // Check database status first - if it's completed, we're done!
            if (data.video_db && data.video_db.status === 'completed') {
                console.log(`✅ Video ${videoId} is complete in database!`);
                processingVideos.delete(videoId);
                
                if (isManual) {
                    showStatusIndicator('completed', 'Video completed! Refreshing...');
                    setTimeout(() => location.reload(), 1500);
                } else {
                    showStatusIndicator('completed', 'Video completed! Page will refresh...');
                    setTimeout(() => location.reload(), 3000);
                }
                return; // Stop checking
            }
            
            // If database shows processing, check HeyGen status
            if (data.heygen_result && data.heygen_result.success && 
                data.heygen_result.details && data.heygen_result.details.status === 'completed') {
                // Video is completed in HeyGen but not yet updated in database
                console.log(`✅ Video ${videoId} completed in HeyGen, waiting for database update...`);
                
                if (isManual) {
                    showStatusIndicator('processing', 'Video completed, updating database...');
                }
            } else {
                // Still processing
                const status = data.heygen_result?.details?.status || 'processing';
                console.log(`⏳ Video ${videoId} still ${status}...`);
                
                if (isManual) {
                    showStatusIndicator('processing', `Video is still ${status}. Please wait...`);
                    setTimeout(() => hideStatusIndicator(), 3000);
                }
            }
        } else {
            console.log(`⚠️ Unexpected response for video ${videoId}: ${response.status}`);
            if (isManual) {
                alert('Error checking video status. Please try again.');
            }
        }
        
    } catch (error) {
        console.error(`❌ Error checking video ${videoId}:`, error);
        if (isManual) {
            alert('Error checking video status. Please try again.');
        }
    }
    
}

function refreshVideoStatus(videoId) {
    console.log(`🔄 Manually refreshing video ${videoId}...`);
    checkVideoStatus(videoId, true);
}

// Avatar carousel functionality
function selectAvatar(avatarId, avatarName) {
    console.log(`🎭 Selected avatar: ${avatarName} (ID: ${avatarId})`);
    
    // Show a nice notification
    showStatusIndicator('success', `Selected avatar: ${avatarName}`);
    
    // You could store the selected avatar in localStorage or session
    localStorage.setItem('selectedAvatarId', avatarId);
    localStorage.setItem('selectedAvatarName', avatarName);
    
    // Optional: Navigate to text-to-video with pre-selected avatar
    // window.location.href = `/text-to-video?avatar=${avatarId}`;
}

// Initialize avatar carousel
function initAvatarCarousel() {
    const carousel = document.getElementById('avatarCarousel');
    if (!carousel) return;
    
    const avatars = carousel.querySelectorAll('.carousel-avatar');
    if (avatars.length === 0) return;
    
    // Adjust animation duration based on number of avatars
    const duration = Math.max(15, avatars.length * 2);
    carousel.style.animationDuration = `${duration}s`;
    
    // Add hover effects
    avatars.forEach(avatar => {
        avatar.addEventListener('mouseenter', () => {
            carousel.style.animationPlayState = 'paused';
        });
        
        avatar.addEventListener('mouseleave', () => {
            carousel.style.animationPlayState = 'running';
        });
    });
}

function showStatusIndicator(status, message) {
    const indicator = document.getElementById('statusIndicator');
    const content = document.getElementById('statusContent');
    
    content.innerHTML = `
        <div style="display: flex; align-items: center; gap: 0.5rem;">
            <i class="fas fa-${status === 'processing' ? 'clock' : status === 'completed' ? 'check-circle' : 'exclamation-triangle'}"></i>
            <span>${message}</span>
        </div>
    `;
    
    indicator.className = `status-indicator show ${status}`;
}

function hideStatusIndicator() {
    const indicator = document.getElementById('statusIndicator');
    indicator.classList.remove('show');
}

// ==================== UI FUNCTIONS ==================== 
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.querySelector('.main-content');
    sidebar.classList.toggle('open');
    mainContent.classList.toggle('full-width');
}

function toggleTheme() {
    const currentTheme = document.body.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.body.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    
    // Update theme icon
    const themeBtn = document.querySelector('.header-btn i');
    themeBtn.className = newTheme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
}

// User dropdown functionality
function toggleUserDropdown() {
    const dropdown = document.getElementById('userDropdown');
    const icon = document.getElementById('dropdownIcon');
    
    dropdown.classList.toggle('show');
    
    if (dropdown.classList.contains('show')) {
        icon.style.transform = 'rotate(180deg)';
    } else {
        icon.style.transform = 'rotate(0deg)';
    }
}

// Logout function
function logout() {
    if (confirm('Are you sure you want to logout?')) {
        window.location.href = '/logout';
    }
}

// Close dropdown when clicking outside
document.addEventListener('click', function(event) {
    const userMenu = document.querySelector('.user-menu');
    const dropdown = document.getElementById('userDropdown');
    
    if (!userMenu.contains(event.target)) {
        dropdown.classList.remove('show');
        document.getElementById('dropdownIcon').style.transform = 'rotate(0deg)';
    }
});

// Prevent dropdown from closing when clicking inside
document.addEventListener('DOMContentLoaded', function() {
    const dropdown = document.getElementById('userDropdown');
    if (dropdown) {
        dropdown.addEventListener('click', function(event) {
            event.stopPropagation();
        });
    }
});

function startCreation(method) {
    // Enhanced creation flow
    console.log('Starting creation with method:', method);
    
    // Show enhanced modal or navigate to creation page
    const messages = {
        'voice': 'Ready to record your voice? Let\'s create an amazing AI video!',
        'text': 'Ready to convert text to speech? Choose your voice and let\'s begin!'
    };
    
    if (confirm(messages[method] + '\n\nWould you like to proceed?')) {
        // Navigate to appropriate creation page based on method
        if (method === 'voice') {
            window.location.href = '/voice-recording';  // Voice recording page
        } else if (method === 'text') {
            window.location.href = '/text-to-video';
        }
    }
}

function showPremiumModal() {
    const features = [
        '✨ Premium Templates',
        '🎨 Custom Backgrounds', 
        '🤖 Interactive Avatars',
        '📝 AI Script Generator',
        '📊 Advanced Analytics',
        '🎯 Priority Support'
    ];
    
    alert('🚀 Premium Features Coming Soon!\n\n' + features.join('\n') + '\n\nUpgrade to unlock advanced AI video creation tools!');
}

function downloadVideo(videoId) {
    window.open(`/api/videos/${videoId}/download`, '_blank');
}

function playVideo(videoId) {
    window.location.href = `/video/${videoId}`;
}

// Load saved theme
const savedTheme = localStorage.getItem('theme');
if (savedTheme) {
    document.body.setAttribute('data-theme', savedTheme);
    if (savedTheme === 'dark') {
        document.querySelector('.header-btn i').className = 'fas fa-sun';
    }
}

// Add smooth scrolling
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// Cleanup when page unloads
window.addEventListener('beforeunload', function() {
    if (videoUpdateInterval) {
        clearInterval(videoUpdateInterval);
    }
});

// Support Avatar Functionality
let supportChatExpanded = false;
let supportConversationId = null;

function toggleSupportChat() {
    const container = document.getElementById('supportChatContainer');
    const icon = document.getElementById('supportToggleIcon');
    
    supportChatExpanded = !supportChatExpanded;
    
    if (supportChatExpanded) {
        container.classList.add('expanded');
        icon.classList.add('rotated');
        
        // Focus on input when opened
        setTimeout(() => {
            document.getElementById('supportInput').focus();
        }, 300);
    } else {
        container.classList.remove('expanded');
        icon.classList.remove('rotated');
    }
}

function handleSupportKeyPress(event) {
    if (event.key === 'Enter') {
        sendSupportMessage();
    }
}

function sendSupportMessage() {
    const input = document.getElementById('supportInput');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Add user message to chat
    addSupportMessage(message, 'user');
    
    // Clear input
    input.value = '';
    
    // Show typing indicator
    showTypingIndicator();
    
    // Send to backend
    fetch('/api/support-chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
            message: message,
            conversation_id: supportConversationId
        })
    })
    .then(response => response.json())
    .then(data => {
        hideTypingIndicator();
        
        if (data.success) {
            supportConversationId = data.conversation_id;
            addSupportMessage(data.response, 'bot');
            
            // Update status if needed
            if (data.admin_notified) {
                updateSupportStatus('Admin notified');
            }
        } else {
            addSupportMessage('Sorry, I encountered an error. Please try again.', 'bot');
        }
    })
    .catch(error => {
        console.error('Support chat error:', error);
        hideTypingIndicator();
        addSupportMessage('Sorry, I\'m having trouble connecting. Please try again later.', 'bot');
    });
}

function sendQuickMessage(message) {
    const input = document.getElementById('supportInput');
    input.value = message;
    sendSupportMessage();
}

function addSupportMessage(message, type) {
    const messagesContainer = document.getElementById('supportMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `support-message ${type}-message`;
    
    const avatar = type === 'bot' ? '🤖' : '👤';
    
    messageDiv.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
            <p>${message}</p>
        </div>
    `;
    
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function showTypingIndicator() {
    const messagesContainer = document.getElementById('supportMessages');
    const typingDiv = document.createElement('div');
    typingDiv.className = 'support-message bot-message typing-indicator';
    typingDiv.id = 'typingIndicator';
    
    typingDiv.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-content">
            <div class="typing-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
    
    messagesContainer.appendChild(typingDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function hideTypingIndicator() {
    const typingIndicator = document.getElementById('typingIndicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
}

function updateSupportStatus(status) {
    const statusElement = document.getElementById('supportStatus');
    statusElement.textContent = status;
    
    // Reset status after 3 seconds
    setTimeout(() => {
        statusElement.textContent = 'Ready to help';
    }, 3000);
}

// === VIDEO URL DEBUG === (Added by advisor)
console.log('=== VIDEO URL DEBUG ===');

// If you're using server-side rendering, check template data
if (typeof videos !== 'undefined') {
    console.log('Template videos data:', videos);
    videos.forEach((video, index) => {
        console.log(`Video ${index}:`, {
            video_path: video.video_path,
            full_object: video
        });
    });
}

// If you're using API calls, intercept the response
const originalFetch = window.fetch;
window.fetch = function(...args) {
    return originalFetch.apply(this, args).then(response => {
        if (args[0].includes('completed-videos')) {
            response.clone().json().then(data => {
                console.log('API Response for completed-videos:', data);
                if (data.videos && Array.isArray(data.videos)) {
                    data.videos.forEach((video, index) => {
                        console.log(`API Video ${index}:`, {
                            id: video.id,
                            video_path: video.video_path,
                            video_url: video.video_url,
                            title: video.title,
                            full_object: video
                        });
                    });
                } else if (Array.isArray(data)) {
                    data.forEach((video, index) => {
                        console.log(`API Video ${index}:`, {
                            id: video.id,
                            video_path: video.video_path,
                            video_url: video.video_url,
                            title: video.title,
                            full_object: video
                        });
                    });
                }
            }).catch(err => console.log('Error parsing API response:', err));
        }
        return response;
    });
};

// Check what URLs are being used for video elements
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(() => {
        const videoElements = document.querySelectorAll('video, source');
        console.log('Found video elements:', videoElements.length);
        
        videoElements.forEach((element, index) => {
            console.log(`Video element ${index}:`, {
                src: element.src,
                tagName: element.tagName,
                outerHTML: element.outerHTML.substring(0, 200)
            });
        });
        
        // Check for any links that might be video-related
        const videoLinks = document.querySelectorAll('a[href*="video"], a[href*="/video/"]');
        console.log('Found video links:', videoLinks.length);
        videoLinks.forEach((link, index) => {
            console.log(`Video link ${index}:`, {
                href: link.href,
                text: link.textContent,
                outerHTML: link.outerHTML.substring(0, 200)
            });
        });
    }, 2000);
});

// Debug any clicks on video-related elements
document.addEventListener('click', function(e) {
    if (e.target.closest('[data-video-id]') || e.target.href && e.target.href.includes('video')) {
        console.log('Video-related click:', {
            target: e.target,
            href: e.target.href,
            dataset: e.target.dataset,
            closest_video_element: e.target.closest('[data-video-id]')
        });
    }
});