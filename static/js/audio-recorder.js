// static/js/audio-recorder.js
// Audio recording functionality for MyAvatar

class AudioRecorder {
  constructor(options = {}) {
    this.options = {
      maxSeconds: options.maxSeconds || 300,
      onTick: options.onTick || (() => {}),
      mimeType: 'audio/webm'
    };
    
    this.mediaRecorder = null;
    this.chunks = [];
    this.startTime = null;
    this.timerInterval = null;
    this.stream = null;
  }

  async start() {
    try {
      // Get microphone access
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      // Determine best mime type
      const mimeTypes = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/ogg;codecs=opus',
        'audio/mp4',
        'audio/mpeg'
      ];
      
      let selectedMimeType = 'audio/webm';
      for (const mimeType of mimeTypes) {
        if (MediaRecorder.isTypeSupported(mimeType)) {
          selectedMimeType = mimeType;
          break;
        }
      }
      
      this.options.mimeType = selectedMimeType;
      console.log('Using mime type:', selectedMimeType);
      
      // Create MediaRecorder
      this.mediaRecorder = new MediaRecorder(this.stream, {
        mimeType: selectedMimeType
      });
      
      this.chunks = [];
      
      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          this.chunks.push(event.data);
        }
      };
      
      this.mediaRecorder.onstop = () => {
        console.log('Recording stopped');
      };
      
      // Start recording
      this.mediaRecorder.start();
      this.startTime = Date.now();
      
      // Start timer
      this.timerInterval = setInterval(() => {
        const elapsed = Math.floor((Date.now() - this.startTime) / 1000);
        const remaining = this.options.maxSeconds - elapsed;
        
        if (remaining <= 0) {
          this.stop();
        } else {
          this.options.onTick(remaining);
        }
      }, 1000);
      
      console.log('Recording started');
      
    } catch (error) {
      console.error('Error starting recording:', error);
      throw error;
    }
  }

  async stop() {
    return new Promise((resolve) => {
      if (!this.mediaRecorder || this.mediaRecorder.state === 'inactive') {
        resolve();
        return;
      }
      
      this.mediaRecorder.onstop = () => {
        // Stop all tracks
        if (this.stream) {
          this.stream.getTracks().forEach(track => track.stop());
        }
        
        // Clear timer
        if (this.timerInterval) {
          clearInterval(this.timerInterval);
          this.timerInterval = null;
        }
        
        console.log('Recording stopped, chunks:', this.chunks.length);
        resolve();
      };
      
      this.mediaRecorder.stop();
    });
  }

  async getBlob() {
    await this.stop();
    
    if (this.chunks.length === 0) {
      throw new Error('No audio data recorded');
    }
    
    const blob = new Blob(this.chunks, { type: this.options.mimeType });
    console.log('Created blob:', blob.size, 'bytes, type:', blob.type);
    return blob;
  }

  getFileExtension() {
    // Return appropriate file extension based on mime type
    const mimeType = this.options.mimeType;
    if (mimeType.includes('webm')) return '.webm';
    if (mimeType.includes('ogg')) return '.ogg';
    if (mimeType.includes('mp4')) return '.mp4';
    if (mimeType.includes('mpeg')) return '.mp3';
    return '.webm'; // default
  }
}

// Only set if not already defined
if (!window.AudioRecorder) {
  window.AudioRecorder = AudioRecorder;
}
