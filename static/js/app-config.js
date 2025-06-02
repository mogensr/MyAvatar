// static/js/app-config.js
// Configuration file for MyAvatar Portal - Version 2.0
// With correct endpoints and enhanced Danish UI text

console.log('=== Loading App Configuration V2 ===');

window.AppConfig = {
  // API Configuration
  api: {
    baseUrl: "", // Empty string means use same domain
    endpoints: {
      // User & Auth
      user: "/api/user",
      debug: "/api/debug",
      
      // Avatar Management
      avatars: "/api/avatars",
      createAvatar: "/api/avatar",
      
      // Video Management
      videos: "/api/videos",
      generateVideo: "/api/video/generate", // CORRECT endpoint with /video/
      videoStatus: "/api/video/status/{video_id}",
      
      // Admin endpoints
      logs: "/api/logs"
    },
    
    // Polling configuration
    pollingInterval: 3000,       // 3 seconds between status checks
    maxPollingAttempts: 100,     // Max ~5 minutes of polling
    
    // Timeouts
    uploadTimeout: 60000,        // 60 seconds for upload
    requestTimeout: 30000        // 30 seconds for regular requests
  },
  
  // UI Configuration
  ui: {
    brandName: "MyAvatar Portal",
    logo: "/static/logo-rye.png",
    
    // Recording settings
    maxRecordingTime: 300,       // 5 minutes max
    defaultRecordingTime: 60,    // 1 minute default
    
    // UI Text (English)
    text: {
      // Headers
      organizationTitle:    "Your Organization",
      avatarsTitle:         "My Avatars",
      videosTitle:          "My Videos",
      recordTitle:          "Record Video",
      
      // Recording
      recordingLabel:       "Recording...",
      processingLabel:      "Processing...",
      uploadingLabel:       "Uploading...",
      generatingLabel:      "Generating video...",
      
      // Instructions
      selectAvatarFirst:    "Please select an avatar first",
      selectAvatar:         "Select an avatar from the 'My Avatars' tab",
      startRecording:       "Click to start recording",
      stopRecording:        "Click to stop recording",
      
      // Status messages
      noAvatarsMessage:     "No avatars yet - contact administrator",
      noVideosMessage:      "You have no videos yet",
      videoReady:           "Video ready!",
      videoFailed:          "Video generation failed",
      
      // Progress
      percentComplete:      "% complete",
      generationFailed:     "Generation failed",
      generationTimeout:    "Generation timed out",
      
      // Errors
      microphoneError:      "Could not access microphone",
      uploadError:          "Upload failed",
      networkError:         "Network error",
      unknownError:         "Unknown error occurred",
      
      // Buttons
      testMicrophone:       "Test Microphone",
      startRecording:       "Start Recording",
      stopRecording:        "Stop Recording",
      retry:                "Try Again",
      download:             "Download",
      play:                 "Play"
    },
    
    // UI Colors and styling
    colors: {
      primary: "#4f46e5",
      success: "#10b981",
      danger: "#dc2626",
      warning: "#f59e0b",
      info: "#3b82f6"
    },
    
    // Feature flags
    features: {
      showDebugInfo: true,      // Show debug info in console
      allowDownload: true,      // Allow video downloads
      showProgress: true,       // Show detailed progress
      autoPlayVideos: false,    // Auto-play generated videos
      enableNotifications: true // Browser notifications when video ready
    }
  },
  
  // Storage settings
  storage: {
    provider: "cloudinary",     // or "local"
    maxFileSize: 50 * 1024 * 1024, // 50MB max
    allowedFormats: ["webm", "mp4", "ogg", "mp3"],
    audioQuality: 0.8
  },
  
  // Debug settings
  debug: {
    enabled: true,
    logLevel: "info", // "error", "warn", "info", "debug"
    logApiCalls: true,
    logAudioData: true
  }
};

// Freeze config to prevent accidental changes
Object.freeze(window.AppConfig);
Object.freeze(window.AppConfig.api);
Object.freeze(window.AppConfig.api.endpoints);
Object.freeze(window.AppConfig.ui);
Object.freeze(window.AppConfig.ui.text);

// Log successful load
console.log('✅ App Configuration loaded successfully');
console.log('API Base URL:', window.AppConfig.api.baseUrl || 'Same domain');
console.log('Generate Video Endpoint:', window.AppConfig.api.endpoints.generateVideo);

// Export for module systems if needed
if (typeof module !== 'undefined' && module.exports) {
  module.exports = window.AppConfig;
}
