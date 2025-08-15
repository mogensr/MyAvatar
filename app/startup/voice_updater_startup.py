"""
Voice Updater Startup Module - Initializes the voice updater on application startup
"""
import threading
import time
from ..logger.log_handler import log_info, log_error
from ..utils.voice_updater import voice_updater

def start_voice_updater():
    """
    Start the voice updater service
    """
    try:
        log_info("Starting voice updater service", "VoiceUpdaterStartup")
        
        # Initial update
        success = voice_updater.fetch_all_voices()
        
        if success:
            voice_updater.update_language_voice_map_in_service()
            voice_updater.validate_user_voice_ids()
            log_info("Initial voice update completed successfully", "VoiceUpdaterStartup")
        else:
            log_error("Initial voice update failed", "VoiceUpdaterStartup")
            
        # Start background thread for periodic updates
        updater_thread = threading.Thread(
            target=_periodic_update_thread,
            daemon=True,
            name="VoiceUpdaterThread"
        )
        updater_thread.start()
        
        log_info("Voice updater background thread started", "VoiceUpdaterStartup")
        return True
    except Exception as e:
        log_error(f"Failed to start voice updater: {e}", "VoiceUpdaterStartup")
        return False

def _periodic_update_thread():
    """
    Background thread for periodic voice updates
    """
    # Update interval in seconds (24 hours)
    update_interval = 24 * 60 * 60
    
    while True:
        try:
            # Sleep first to avoid immediate re-update after initial update
            time.sleep(update_interval)
            
            log_info("Running periodic voice update", "VoiceUpdaterThread")
            voice_updater.update_if_needed()
            
        except Exception as e:
            log_error(f"Error in voice updater thread: {e}", "VoiceUpdaterThread")
            # Sleep a bit to avoid tight loop in case of persistent errors
            time.sleep(60)
