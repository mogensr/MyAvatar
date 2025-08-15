/**
 * Avatar Selection Module
 * Handles fetching and selecting public avatars from HeyGen
 */

const AvatarSelection = {
    // Cache for avatars
    avatars: [],
    userType: null,
    
    /**
     * Initialize the avatar selection module
     */
    init: function() {
        console.log('Initializing Avatar Selection Module');
        this.setupEventListeners();
    },
    
    /**
     * Set up event listeners
     */
    setupEventListeners: function() {
        // Fetch avatars button
        const fetchButton = document.getElementById('fetch-avatars-btn');
        if (fetchButton) {
            fetchButton.addEventListener('click', this.fetchPublicAvatars.bind(this));
        }
        
        // Avatar selection container
        const avatarContainer = document.getElementById('public-avatars-container');
        if (avatarContainer) {
            avatarContainer.addEventListener('click', this.handleAvatarClick.bind(this));
        }
    },
    
    /**
     * Fetch public avatars from HeyGen
     */
    fetchPublicAvatars: async function() {
        try {
            // Show loading state
            this.showLoading(true);
            
            // Fetch avatars from API
            const response = await fetch('/trial/public-avatars');
            const data = await response.json();
            
            if (data.success) {
                this.avatars = data.avatars;
                this.userType = data.user_type;
                
                // Display avatars
                this.displayAvatars(data.avatars);
                
                // Show success message
                this.showMessage(`Found ${data.count} public avatars`, 'success');
            } else {
                this.showMessage('Failed to fetch avatars', 'error');
            }
        } catch (error) {
            console.error('Error fetching public avatars:', error);
            this.showMessage('Error fetching avatars', 'error');
        } finally {
            this.showLoading(false);
        }
    },
    
    /**
     * Display avatars in the UI
     * @param {Array} avatars - List of avatars to display
     */
    displayAvatars: function(avatars) {
        const container = document.getElementById('public-avatars-container');
        if (!container) return;
        
        // Clear existing avatars
        container.innerHTML = '';
        
        // Group avatars by group name
        const groupedAvatars = {};
        avatars.forEach(avatar => {
            const groupName = avatar.group_name || 'Other';
            if (!groupedAvatars[groupName]) {
                groupedAvatars[groupName] = [];
            }
            groupedAvatars[groupName].push(avatar);
        });
        
        // Create HTML for each group
        Object.keys(groupedAvatars).forEach(groupName => {
            const groupDiv = document.createElement('div');
            groupDiv.className = 'avatar-group mb-4';
            
            // Group header
            const groupHeader = document.createElement('h4');
            groupHeader.className = 'mb-3';
            groupHeader.textContent = groupName;
            groupDiv.appendChild(groupHeader);
            
            // Avatars grid
            const avatarsGrid = document.createElement('div');
            avatarsGrid.className = 'row row-cols-2 row-cols-md-4 g-3';
            
            // Add avatars to grid
            groupedAvatars[groupName].forEach(avatar => {
                const avatarCol = document.createElement('div');
                avatarCol.className = 'col';
                
                const avatarCard = document.createElement('div');
                avatarCard.className = 'card h-100 avatar-card';
                avatarCard.dataset.avatarId = avatar.id;
                avatarCard.dataset.imageUrl = avatar.image_url;
                
                // Avatar image
                const img = document.createElement('img');
                img.src = avatar.image_url;
                img.className = 'card-img-top avatar-image';
                img.alt = 'Avatar';
                
                // Card body
                const cardBody = document.createElement('div');
                cardBody.className = 'card-body';
                
                // Select button
                const selectBtn = document.createElement('button');
                selectBtn.className = 'btn btn-primary btn-sm w-100 select-avatar-btn';
                selectBtn.textContent = 'Select';
                selectBtn.dataset.avatarId = avatar.id;
                
                // Append elements
                cardBody.appendChild(selectBtn);
                avatarCard.appendChild(img);
                avatarCard.appendChild(cardBody);
                avatarCol.appendChild(avatarCard);
                avatarsGrid.appendChild(avatarCol);
            });
            
            groupDiv.appendChild(avatarsGrid);
            container.appendChild(groupDiv);
        });
        
        // Show the container
        container.style.display = 'block';
    },
    
    /**
     * Handle avatar selection
     * @param {Event} event - Click event
     */
    handleAvatarClick: async function(event) {
        // Check if a select button was clicked
        if (!event.target.classList.contains('select-avatar-btn')) return;
        
        const avatarId = event.target.dataset.avatarId;
        if (!avatarId) return;
        
        try {
            // Find the avatar data
            const avatar = this.avatars.find(a => a.id === avatarId);
            if (!avatar) return;
            
            // Show loading state
            this.showLoading(true);
            
            // Prepare data for API
            const avatarData = {
                avatar_id: avatar.id,
                avatar_name: `HeyGen Avatar ${avatar.id.substring(0, 6)}`,
                avatar_image_url: avatar.image_url
            };
            
            // Call API to select avatar
            const response = await fetch('/trial/select-public-avatar', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(avatarData)
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Show success message
                this.showMessage('Avatar selected successfully', 'success');
                
                // If this is a paid user, show additional message about team membership
                if (this.userType !== 'trial') {
                    this.showMessage('HeyGen team membership will be updated', 'info');
                }
                
                // Refresh avatar display in the UI
                // This would typically update the current avatar display elsewhere in the UI
                this.triggerAvatarRefresh();
            } else {
                this.showMessage('Failed to select avatar', 'error');
            }
        } catch (error) {
            console.error('Error selecting avatar:', error);
            this.showMessage('Error selecting avatar', 'error');
        } finally {
            this.showLoading(false);
        }
    },
    
    /**
     * Trigger a refresh of the avatar display in the UI
     */
    triggerAvatarRefresh: function() {
        // Dispatch a custom event that other components can listen for
        const event = new CustomEvent('avatar-updated');
        document.dispatchEvent(event);
        
        // If we're on the dashboard, refresh the avatar display
        if (typeof refreshUserAvatars === 'function') {
            refreshUserAvatars();
        }
    },
    
    /**
     * Show a message to the user
     * @param {string} message - Message to display
     * @param {string} type - Message type (success, error, info)
     */
    showMessage: function(message, type = 'info') {
        // Use the existing notification system if available
        if (typeof showNotification === 'function') {
            showNotification(message, type);
            return;
        }
        
        // Fallback to alert
        alert(message);
    },
    
    /**
     * Show or hide loading state
     * @param {boolean} isLoading - Whether loading is in progress
     */
    showLoading: function(isLoading) {
        const loadingSpinner = document.getElementById('avatar-loading-spinner');
        if (loadingSpinner) {
            loadingSpinner.style.display = isLoading ? 'block' : 'none';
        }
        
        // Disable fetch button during loading
        const fetchButton = document.getElementById('fetch-avatars-btn');
        if (fetchButton) {
            fetchButton.disabled = isLoading;
        }
    }
};

// Initialize when the DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    AvatarSelection.init();
});
