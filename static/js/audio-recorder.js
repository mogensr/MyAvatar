// static/js/audio-recorder.js
// Only define AudioRecorder if it doesn't already exist
if (!window.AudioRecorder) {
  class AudioRecorder {
    constructor({ mimeType = null, maxSeconds = 300, onTick } = {}) {
      this.mimeType = mimeType || this.getBestMimeType(); // Auto-detect best format
      this.maxSeconds = maxSeconds;
      this.onTick = onTick;
      this.chunks = [];
      this.recorder = null;
      this.timerId = null;
      this.startedAt = null;
    }

    static async getMicrophone() {
      return navigator.mediaDevices.getUserMedia({ audio: true });
    }
    
    // NEW: Get best compatible MIME type for HeyGen
    getBestMimeType() {
      // Priority list - formats HeyGen accepts directly
      const mimeTypes = [
        'audio/mp3',
        'audio/mpeg',  // Alternative MP3 mime type
        'audio/wav', 
        'audio/m4a',
        'audio/aac',
        'audio/webm' // Fallback for Chrome/Edge
      ];
      
      for (const type of mimeTypes) {
        if (MediaRecorder.isTypeSupported(type)) {
          console.log(`Using format: ${type}`);
          return type;
        }
      }
      
      // Default fallback
      console.log('Using default browser format');
      return 'audio/webm';
    }

    async init() {
      if (this.recorder) return;
      const stream = await AudioRecorder.getMicrophone();
      this.recorder = new MediaRecorder(stream, { mimeType: this.mimeType });
      this.recorder.ondataavailable = e => this.chunks.push(e.data);
    }

    async start() {
      await this.init();
      this.chunks = [];
      this.recorder.start();
      this.startedAt = Date.now();
      if (this.onTick) {
        this.timerId = setInterval(() => {
          const sec = Math.floor((Date.now() - this.startedAt) / 1000);
          const remain = this.maxSeconds - sec;
          if (remain <= 0) this.stop();
          else this.onTick(remain);
        }, 1000);
      }
    }

    stop() {
      if (this.recorder && this.recorder.state === "recording") this.recorder.stop();
      clearInterval(this.timerId);
      
      // Release microphone access
      if (this.recorder && this.recorder.stream) {
        this.recorder.stream.getTracks().forEach(track => track.stop());
      }
    }

    async getBlob() {
      if (this.recorder && this.recorder.state === "recording")
        await new Promise(r => (this.recorder.onstop = r, this.stop()));
      return new Blob(this.chunks, { type: this.mimeType });
    }
    
    // NEW: Get file extension based on MIME type
    getFileExtension() {
      const mimeType = this.mimeType.toLowerCase();
      if (mimeType.includes('mp3') || mimeType.includes('mpeg')) return '.mp3';
      if (mimeType.includes('wav')) return '.wav';
      if (mimeType.includes('m4a')) return '.m4a';
      if (mimeType.includes('aac')) return '.aac';
      if (mimeType.includes('webm')) return '.webm';
      return '';
    }
  }

  window.AudioRecorder = AudioRecorder;
}