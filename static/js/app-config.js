// static/js/app-config.js
// Configuration file for MyAvatar Portal

window.AppConfig = {
  api: {

    baseUrl: "",

  

    endpoints: {
      user: "/api/user",
      avatars: "/api/avatars",
      videos: "/api/videos",
      generateVideo: "/api/video/generate",
      videoStatus: "/api/video/status/{video_id}",
      updateBackground: "/api/video/background"
    },
    pollingInterval: 5000,       // ms mellem status-polls
    maxPollingAttempts: 60       // stop efter 60 forsøg
  },
  ui: {
    brandName: "MyAvatar Portal",
    logo: "/static/logo-rye.png",
    maxRecordingTime: 300,       // 5 minutter
    text: {
      organizationTitle:    "Din organisation",
      avatarsTitle:         "Dine avatarer",
      recordTitle:          "Optag og generer video",
      recordingLabel:       "Optager…",
      selectAvatarFirst:    "Vælg en avatar og optag lyd først",
      recentVideosTitle:    "Seneste videoer",
      noVideosMessage:      "Du har ingen videoer endnu",
      percentComplete:      "fuldført",
      generationFailed:     "Generering fejlede"
    }
  }
};
