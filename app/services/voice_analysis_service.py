"""
Voice Analysis Service for MyAvatar

This service analyzes voice recordings to extract natural characteristics
such as speed, pitch, and emotional tone for more natural text-to-video generation.
"""

import os
import tempfile
import logging
import numpy as np
import librosa
import soundfile as sf
from pydub import AudioSegment
try:
    import webrtcvad
    WEBRTCVAD_AVAILABLE = True
except ImportError:
    WEBRTCVAD_AVAILABLE = False
    webrtcvad = None

from typing import Dict, Any, Tuple, Optional

from ..logger.log_handler import log_info, log_error, log_warning

class VoiceAnalysisService:
    """Service for analyzing voice recordings and extracting natural characteristics."""
    
    def __init__(self):
        """Initialize the voice analysis service."""
        if WEBRTCVAD_AVAILABLE:
            self.vad = webrtcvad.Vad(3)  # Voice Activity Detection with aggressiveness level 3
            log_info("Voice Analysis Service initialized with webrtcvad", "VoiceAnalysis")
        else:
            self.vad = None
            log_warning("Voice Analysis Service initialized without webrtcvad (not available)", "VoiceAnalysis")
    
    async def analyze_voice(self, audio_file_path: str) -> Dict[str, Any]:
        """
        Analyze a voice recording to extract natural characteristics.
        
        Args:
            audio_file_path: Path to the audio file
            
        Returns:
            Dictionary containing extracted voice characteristics
        """
        try:
            log_info(f"Analyzing voice recording: {audio_file_path}", "VoiceAnalysis")
            
            # Convert to WAV format if needed
            wav_file = self._ensure_wav_format(audio_file_path)
            
            # Load audio file
            y, sr = librosa.load(wav_file, sr=None)
            
            # Extract voice characteristics
            speed = self._analyze_speech_rate(y, sr)
            pitch = self._analyze_pitch(y, sr)
            emotion = self._analyze_emotion(y, sr)
            
            # Clean up temporary file if created
            if wav_file != audio_file_path:
                os.remove(wav_file)
            
            result = {
                "speed": speed,
                "pitch": pitch,
                "emotion": emotion,
                "success": True
            }
            
            log_info(f"Voice analysis complete: {result}", "VoiceAnalysis")
            return result
            
        except Exception as e:
            log_error(f"Error analyzing voice: {str(e)}", "VoiceAnalysis")
            return {
                "success": False,
                "error": str(e),
                "speed": 1.0,  # Default values
                "pitch": 1.0,
                "emotion": "Friendly"
            }
    
    def _ensure_wav_format(self, audio_file_path: str) -> str:
        """
        Ensure the audio file is in WAV format for analysis.
        
        Args:
            audio_file_path: Path to the audio file
            
        Returns:
            Path to WAV file (either original or converted)
        """
        file_ext = os.path.splitext(audio_file_path)[1].lower()
        
        if file_ext == '.wav':
            return audio_file_path
        
        try:
            # Create temporary WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Convert to WAV using pydub
            audio = AudioSegment.from_file(audio_file_path)
            audio.export(temp_path, format="wav")
            
            return temp_path
            
        except Exception as e:
            log_error(f"Error converting audio to WAV: {str(e)}", "VoiceAnalysis")
            return audio_file_path  # Return original path if conversion fails
    
    def _analyze_speech_rate(self, y: np.ndarray, sr: int) -> float:
        """
        Analyze speech rate from audio data.
        
        Args:
            y: Audio time series
            sr: Sample rate
            
        Returns:
            Normalized speech rate (1.0 is average)
        """
        try:
            # Detect onsets for syllable estimation
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)
            
            # Calculate speech rate based on number of onsets and duration
            duration = librosa.get_duration(y=y, sr=sr)
            if duration == 0:
                return 1.0
                
            # Number of onsets per second
            speech_rate = len(onsets) / duration
            
            # Normalize speech rate (1.0 is average, range 0.5-2.0)
            # Average speech rate is about 5-6 syllables per second
            normalized_rate = speech_rate / 5.5
            
            # Clamp to valid range for HeyGen API
            return max(0.5, min(normalized_rate, 2.0))
            
        except Exception as e:
            log_warning(f"Error analyzing speech rate: {str(e)}", "VoiceAnalysis")
            return 1.0  # Default to normal speed
    
    def _analyze_pitch(self, y: np.ndarray, sr: int) -> float:
        """
        Analyze pitch characteristics from audio data.
        
        Args:
            y: Audio time series
            sr: Sample rate
            
        Returns:
            Normalized pitch value (1.0 is average)
        """
        try:
            # Extract pitch using librosa
            pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
            
            # Get indices of pitches with highest magnitude
            indices = np.argmax(magnitudes, axis=0)
            
            # Extract pitches with highest magnitude
            valid_pitches = []
            for i, index in enumerate(indices):
                if magnitudes[index, i] > 0:  # Only include if magnitude is significant
                    valid_pitches.append(pitches[index, i])
            
            if not valid_pitches:
                return 1.0
                
            # Calculate average pitch
            avg_pitch = np.mean(valid_pitches)
            
            # Normalize pitch based on average human voice pitch
            # Average male pitch: ~120Hz, Average female pitch: ~210Hz
            # Use 165Hz as the middle point (1.0)
            normalized_pitch = avg_pitch / 165.0
            
            # Clamp to valid range for HeyGen API
            return max(0.5, min(normalized_pitch, 1.5))
            
        except Exception as e:
            log_warning(f"Error analyzing pitch: {str(e)}", "VoiceAnalysis")
            return 1.0  # Default to normal pitch
    
    def _analyze_emotion(self, y: np.ndarray, sr: int) -> str:
        """
        Analyze emotional tone from audio data.
        
        Args:
            y: Audio time series
            sr: Sample rate
            
        Returns:
            Detected emotion (one of: Friendly, Excited, Serious, Soothing, Broadcaster)
        """
        try:
            # Extract audio features
            # Spectral centroid - brightness of sound
            centroid = librosa.feature.spectral_centroid(y=y, sr=sr).mean()
            
            # RMS energy - volume/intensity
            rms = librosa.feature.rms(y=y).mean()
            
            # Zero crossing rate - noisiness/harshness
            zcr = librosa.feature.zero_crossing_rate(y).mean()
            
            # Spectral contrast - difference between peaks and valleys
            contrast = librosa.feature.spectral_contrast(y=y, sr=sr).mean()
            
            # Simple rule-based emotion classification
            # This is a simplified approach - a real system would use ML models
            
            # High energy, high centroid, high ZCR -> Excited
            if rms > 0.1 and centroid > 2000 and zcr > 0.1:
                return "Excited"
                
            # Low energy, low centroid, low ZCR -> Soothing
            elif rms < 0.05 and centroid < 1500 and zcr < 0.05:
                return "Soothing"
                
            # High contrast, medium centroid -> Broadcaster
            elif contrast > 20 and 1800 < centroid < 2200:
                return "Broadcaster"
                
            # Medium-low energy, low-medium centroid -> Serious
            elif rms < 0.08 and centroid < 1800:
                return "Serious"
                
            # Default to Friendly
            else:
                return "Friendly"
                
        except Exception as e:
            log_warning(f"Error analyzing emotion: {str(e)}", "VoiceAnalysis")
            return "Friendly"  # Default to friendly tone
