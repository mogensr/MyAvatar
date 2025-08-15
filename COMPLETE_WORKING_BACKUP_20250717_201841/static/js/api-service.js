// static/js/api-service.js
// Central API-service til MyAvatar-backend - Version 2.1
// Fixed FormData handling for FastAPI

console.log('=== API Service V2.1 Loading ===');

// ============================================
// CONFIGURATION & SETUP
// ============================================
const { baseUrl, endpoints, pollingInterval, maxPollingAttempts } = window.AppConfig.api;

// Token management
function getTokenFromCookie() {
  const cookie = document.cookie.split(';')
    .map(c => c.trim())
    .find(c => c.startsWith('access_token='));
  
  if (cookie) {
    const token = cookie.split('=')[1];
    console.log('Token found in cookie');
    return token;
  }
  
  console.log('No token found in cookie');
  return null;
}

// ============================================
// API SERVICE CLASS
// ============================================
class APIService {
  // Get current auth token
  static getAuthHeaders() {
    const token = getTokenFromCookie();
    const headers = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  }

  // JSON API helper - for regular JSON endpoints
  static async _json(path, options = {}) {
    const url = baseUrl + path;
    console.log(`API JSON Request: ${options.method || 'GET'} ${url}`);
    
    const defaultOptions = {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders()
      },
      credentials: 'include'
    };
    
    const mergedOptions = {
      ...defaultOptions,
      ...options,
      headers: {
        ...defaultOptions.headers,
        ...options.headers
      }
    };
    
    try {
      const response = await fetch(url, mergedOptions);
      const responseText = await response.text();
      
      console.log(`API Response: ${response.status} ${response.statusText}`);
      
      if (!response.ok) {
        console.error('API Error Response:', responseText);
        throw new Error(`API Error ${response.status}: ${responseText}`);
      }
      
      // Try to parse as JSON
      try {
        const data = JSON.parse(responseText);
        console.log('API Response Data:', data);
        return data;
      } catch (e) {
        console.error('Failed to parse JSON response:', e);
        throw new Error('Invalid JSON response from server');
      }
    } catch (error) {
      console.error('API Request Failed:', error);
      throw error;
    }
  }

  // ============================================
  // USER / AVATARS / VIDEOS ENDPOINTS
  // ============================================
  static async getCurrentUser() {
    console.log('Getting current user...');
    return this._json(endpoints.user);
  }
  
  static async getAvatars() {
    console.log('Getting avatars...');
    return this._json(endpoints.avatars);
  }
  
  static async getVideos() {
    console.log('Getting videos...');
    return this._json(endpoints.videos);
  }

  // ============================================
  // GENERATE VIDEO - CRITICAL FUNCTION
  // ============================================
  static async generateVideo(blob, avatarId) {
    console.log('=== GENERATE VIDEO API CALL ===');
    console.log('Blob info:', {
      size: blob.size,
      type: blob.type,
      isBlob: blob instanceof Blob
    });
    console.log('Avatar ID:', avatarId);
    
    // Validate inputs
    if (!blob || blob.size === 0) {
      throw new Error('Invalid audio blob - no data');
    }
    
    if (!avatarId) {
      throw new Error('Avatar ID is required');
    }
    
    // Create FormData
    const formData = new FormData();
    
    // CRITICAL: FastAPI expects the file field to be named 'audio_file' not 'audio'
    // And the filename should match what the backend expects
    const filename = 'recording.webm';
    
    // Append data to FormData with correct field names
    formData.append('audio', blob, filename);  // Changed from 'audio' to 'audio_file'
    formData.append('avatar_id', avatarId);  // No need for toString()
    
    // Debug FormData contents
    console.log('FormData contents:');
    for (let [key, value] of formData.entries()) {
      if (value instanceof File) {
        console.log(`  ${key}: File(${value.name}, ${value.size} bytes, ${value.type})`);
      } else {
        console.log(`  ${key}: ${value}`);
      }
    }
    
    const url = baseUrl + endpoints.generateVideo;
    console.log('Uploading to:', url);
    
    try {
      // CRITICAL: For FormData, we must NOT set Content-Type header
      // The browser will set it automatically with the correct boundary
      const headers = this.getAuthHeaders();
      // Do NOT add Content-Type for FormData!
      
      console.log('Request headers:', headers);
      
      const response = await fetch(url, {
        method: 'POST',
        body: formData,
        credentials: 'include',
        headers: headers // Only auth headers, NO Content-Type
      });
      
      const responseText = await response.text();
      console.log(`Upload response: ${response.status} ${response.statusText}`);
      
      if (!response.ok) {
        console.error('Upload failed:', responseText);
        
        // Try to parse error message
        try {
          const errorData = JSON.parse(responseText);
          if (errorData.detail) {
            // FastAPI validation error format
            if (Array.isArray(errorData.detail)) {
              const errors = errorData.detail.map(e => `${e.loc.join('.')}: ${e.msg}`).join(', ');
              throw new Error(`Validation error: ${errors}`);
            } else {
              throw new Error(errorData.detail);
            }
          }
        } catch (e) {
          // If not JSON, use raw text
        }
        
        throw new Error(`Video generation failed: ${response.status} - ${responseText}`);
      }
      
      // Parse response
      try {
        const data = JSON.parse(responseText);
        console.log('Upload success! Response:', data);
        
        if (!data.video_id) {
          throw new Error('No video_id in response');
        }
        
        return data;
      } catch (e) {
        console.error('Failed to parse response:', e);
        throw new Error('Invalid response from server');
      }
      
    } catch (error) {
      console.error('=== UPLOAD ERROR ===');
      console.error(error);
      throw error;
    }
  }

  // ============================================
  // POLL VIDEO STATUS
  // ============================================
  static async pollVideoStatus(videoId, onProgress) {
    console.log('=== POLLING VIDEO STATUS ===');
    console.log('Video ID:', videoId);
    
    let attempts = 0;
    const maxAttempts = maxPollingAttempts || 60; // Default 60 attempts
    const interval = pollingInterval || 2000; // Default 2 seconds
    
    return new Promise((resolve, reject) => {
      const checkStatus = async () => {
        try {
          attempts++;
          console.log(`Poll attempt ${attempts}/${maxAttempts}`);
          
          const url = endpoints.videoStatus.replace("{video_id}", videoId);
          const data = await this._json(url);
          
          console.log('Video status:', data);
          
          // Check if completed
          if (data.status === "completed") {
            console.log('✅ Video generation completed!');
            return resolve(data);
          }
          
          // Check if failed
          if (data.status === "failed" || data.status === "error") {
            console.error('❌ Video generation failed');
            return reject(new Error(data.error || 'Video generation failed'));
          }
          
          // Check if max attempts reached
          if (attempts >= maxAttempts) {
            console.error('❌ Polling timeout');
            return reject(new Error('Video generation timeout - took too long'));
          }
          
          // Update progress
          const progress = data.progress || Math.min(attempts * 2, 90); // Estimate if no progress
          if (onProgress) {
            onProgress(progress);
          }
          
          // Continue polling
          console.log(`Status: ${data.status}, Progress: ${progress}%, Next check in ${interval}ms`);
          setTimeout(checkStatus, interval);
          
        } catch (error) {
          console.error('Poll error:', error);
          reject(error);
        }
      };
      
      // Start polling
      checkStatus();
    });
  }

  // ============================================
  // UTILITY FUNCTIONS
  // ============================================
  
  // Test API connection
  static async testConnection() {
    console.log('Testing API connection...');
    try {
      const user = await this.getCurrentUser();
      console.log('✅ API connection successful:', user);
      return true;
    } catch (error) {
      console.error('❌ API connection failed:', error);
      return false;
    }
  }
  
  // Debug function to check what's being sent
  static debugFormData(formData) {
    console.log('=== FormData Debug ===');
    for (let [key, value] of formData.entries()) {
      if (value instanceof File || value instanceof Blob) {
        console.log(`${key}:`, {
          name: value.name || 'unnamed',
          size: value.size,
          type: value.type,
          lastModified: value.lastModified
        });
      } else {
        console.log(`${key}:`, value);
      }
    }
  }
}

// ============================================
// EXPORT TO WINDOW
// ============================================
window.APIService = APIService;
console.log('✅ API Service V2.1 loaded and ready!');

// Test connection on load (optional)
APIService.testConnection().then(connected => {
  if (connected) {
    console.log('✅ API Service initialized successfully');
  } else {
    console.warn('⚠️ API Service could not connect to backend');
  }
});
