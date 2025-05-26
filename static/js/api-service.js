// static/js/api-service.js
// Central API-service til MyAvatar-backend

const { baseUrl, endpoints, pollingInterval, maxPollingAttempts } = window.AppConfig.api;

// Funktion til at hente token fra cookie (hvis JWT ligger i access_token)
function getTokenFromCookie() {
  return document.cookie.split(';')
    .map(c => c.trim().split('='))
    .find(([name]) => name === 'access_token')?.[1] || null;
}

const defaultHeaders = { "Content-Type": "application/json" };
const token = getTokenFromCookie();
if (token) defaultHeaders["Authorization"] = token;

const defaultOptions = {
  headers: defaultHeaders,
  credentials: 'include'  // sender cookies med
};

class APIService {
  static async _json(path, options = {}) {
    const mergedOptions = {
      ...defaultOptions,
      ...options,
      headers: { ...defaultOptions.headers, ...options.headers }
    };
    const r = await fetch(baseUrl + path, mergedOptions);
    if (!r.ok) throw new Error(`${r.status} – ${r.statusText}`);
    return r.json();
  }

  /* ----------  USER / AVATARS / VIDEOS ---------- */
  static getCurrentUser() { return this._json(endpoints.user); }
  static getAvatars()     { return this._json(endpoints.avatars); }
  static getVideos()      { return this._json(endpoints.videos); }

  /* ----------  GENERATE + POLL VIDEO ---------- */
  static async generateVideo(blob, avatarId) {
    const fd = new FormData();
    
    // UPDATED: Use file extension based on recorded audio format
    const fileExtension = window.recorder?.getFileExtension() || '.webm';
    fd.append("audio", blob, `recording${fileExtension}`);
    fd.append("avatar_id", avatarId);

    // Update status UI if element exists
    const statusElement = document.getElementById('uploadStatus');
    if (statusElement) statusElement.textContent = 'Uploading...';

    try {
      // Vi fjerner headers her, da fetch selv sætter boundary for FormData
      const r = await fetch(baseUrl + endpoints.generateVideo, {
        ...defaultOptions,
        method: "POST",
        body: fd
      });
      
      if (!r.ok) {
        const errorText = await r.text();
        throw new Error(`Video-generering fejlede: ${r.status} - ${errorText}`);
      }
      
      // Update status on success
      if (statusElement) statusElement.textContent = 'Upload successful!';
      
      return r.json();
    } catch (error) {
      // Handle and log error
      console.error('Upload error:', error);
      if (statusElement) statusElement.textContent = 'Upload fejlede: ' + error.message;
      throw error;
    }
  }

  static pollVideoStatus(videoId, onProgress) {
    let attempts = 0;
    return new Promise((resolve, reject) => {
      const check = async () => {
        try {
          const data = await this._json(
            endpoints.videoStatus.replace("{video_id}", videoId)
          );
          if (data.status === "completed") return resolve(data);
          if (++attempts > maxPollingAttempts) {
            return reject(new Error("Status-polling timede ud"));
          }
          onProgress?.(data.progress ?? 0);
          setTimeout(check, pollingInterval);
        } catch (err) {
          reject(err);
        }
      };
      check();
    });
  }
}

window.APIService = APIService;
