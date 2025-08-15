"""
File Change Tracker for MyAvatar Project
Monitors all file changes and logs them with detailed information
"""
import os
import time
import json
import hashlib
from datetime import datetime
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from ..logger.log_handler import log_info, log_warning, log_error

class FileChangeTracker(FileSystemEventHandler):
    """
    Advanced file change tracker that logs all modifications, creations, and deletions
    """
    
    def __init__(self, project_root: str, log_file: str = "changes.log"):
        self.project_root = Path(project_root)
        self.log_file = self.project_root / log_file
        self.changes_json = self.project_root / "changes.json"
        self.file_hashes = {}
        
        # Ignore patterns
        self.ignore_patterns = {
            '__pycache__',
            '.git',
            '.env',
            'node_modules',
            '.vscode',
            '.idea',
            '*.pyc',
            '*.log',
            'changes.json',
            'changes.log'
        }
        
        # Initialize log files
        self._initialize_logs()
        self._load_existing_hashes()
    
    def _initialize_logs(self):
        """Initialize log files with headers"""
        if not self.log_file.exists():
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write(f"=== MyAvatar Project Change Log - Started {datetime.now()} ===\n")
                f.write("Format: [TIMESTAMP] [EVENT_TYPE] [FILE_PATH] [DETAILS]\n\n")
        
        if not self.changes_json.exists():
            with open(self.changes_json, 'w', encoding='utf-8') as f:
                json.dump({"changes": [], "started": datetime.now().isoformat()}, f, indent=2)
    
    def _load_existing_hashes(self):
        """Load existing file hashes to detect actual content changes"""
        try:
            for file_path in self.project_root.rglob("*"):
                if file_path.is_file() and not self._should_ignore(file_path):
                    try:
                        with open(file_path, 'rb') as f:
                            content = f.read()
                            self.file_hashes[str(file_path)] = hashlib.md5(content).hexdigest()
                    except (PermissionError, UnicodeDecodeError):
                        pass
        except Exception as e:
            log_error("Error loading existing file hashes", "FileTracker", e)
    
    def _should_ignore(self, file_path: Path) -> bool:
        """Check if file should be ignored based on patterns"""
        path_str = str(file_path.relative_to(self.project_root))
        
        for pattern in self.ignore_patterns:
            if pattern in path_str or file_path.name.startswith('.'):
                return True
        return False
    
    def _get_file_info(self, file_path: str) -> dict:
        """Get detailed file information"""
        try:
            path = Path(file_path)
            stat = path.stat()
            
            # Try to get file hash for content change detection
            file_hash = None
            if path.is_file():
                try:
                    with open(path, 'rb') as f:
                        content = f.read()
                        file_hash = hashlib.md5(content).hexdigest()
                except (PermissionError, UnicodeDecodeError):
                    pass
            
            return {
                "size": stat.st_size if path.is_file() else 0,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "hash": file_hash,
                "extension": path.suffix,
                "is_code_file": path.suffix in ['.py', '.js', '.html', '.css', '.sql', '.json', '.yaml', '.toml']
            }
        except Exception:
            return {}
    
    def _log_change(self, event_type: str, file_path: str, details: dict = None):
        """Log change to both text and JSON files"""
        timestamp = datetime.now()
        relative_path = str(Path(file_path).relative_to(self.project_root))
        
        # Skip if should be ignored
        if self._should_ignore(Path(file_path)):
            return
        
        # Get file info
        file_info = self._get_file_info(file_path)
        
        # Check if it's actually a content change (not just timestamp)
        if event_type == "MODIFIED" and file_info.get("hash"):
            old_hash = self.file_hashes.get(file_path)
            new_hash = file_info["hash"]
            if old_hash == new_hash:
                return  # No actual content change
            self.file_hashes[file_path] = new_hash
        
        # Log to text file
        log_entry = f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] [{event_type}] {relative_path}"
        if details:
            log_entry += f" - {details}"
        
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry + "\n")
        except Exception as e:
            log_error("Error writing to change log", "FileTracker", e)
        
        # Log to JSON file
        change_record = {
            "timestamp": timestamp.isoformat(),
            "event_type": event_type,
            "file_path": relative_path,
            "full_path": file_path,
            "file_info": file_info,
            "details": details or {}
        }
        
        try:
            # Read existing JSON
            with open(self.changes_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Add new change
            data["changes"].append(change_record)
            data["last_updated"] = timestamp.isoformat()
            
            # Keep only last 1000 changes to prevent file from getting too large
            if len(data["changes"]) > 1000:
                data["changes"] = data["changes"][-1000:]
            
            # Write back
            with open(self.changes_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            log_error("Error writing to changes JSON", "FileTracker", e)
        
        # Also log to main application log
        log_info(f"File change detected: {event_type} - {relative_path}", "FileTracker")
    
    def on_modified(self, event):
        """Handle file modification events"""
        if not event.is_directory:
            self._log_change("MODIFIED", event.src_path, {"reason": "File content changed"})
    
    def on_created(self, event):
        """Handle file creation events"""
        if not event.is_directory:
            self._log_change("CREATED", event.src_path, {"reason": "New file created"})
        else:
            self._log_change("DIR_CREATED", event.src_path, {"reason": "New directory created"})
    
    def on_deleted(self, event):
        """Handle file deletion events"""
        if not event.is_directory:
            self._log_change("DELETED", event.src_path, {"reason": "File deleted"})
            # Remove from hash tracking
            if event.src_path in self.file_hashes:
                del self.file_hashes[event.src_path]
        else:
            self._log_change("DIR_DELETED", event.src_path, {"reason": "Directory deleted"})
    
    def on_moved(self, event):
        """Handle file move/rename events"""
        if not event.is_directory:
            self._log_change("MOVED", event.dest_path, {
                "reason": "File moved/renamed",
                "from": str(Path(event.src_path).relative_to(self.project_root)),
                "to": str(Path(event.dest_path).relative_to(self.project_root))
            })
            # Update hash tracking
            if event.src_path in self.file_hashes:
                self.file_hashes[event.dest_path] = self.file_hashes.pop(event.src_path)


class FileChangeService:
    """
    Service to manage file change tracking
    """
    
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.observer = None
        self.tracker = None
    
    def start_tracking(self):
        """Start the file change tracking service"""
        try:
            self.tracker = FileChangeTracker(self.project_root)
            self.observer = Observer()
            self.observer.schedule(self.tracker, self.project_root, recursive=True)
            self.observer.start()
            
            log_info("File change tracking service started", "FileTracker")
            return True
            
        except Exception as e:
            log_error("Failed to start file change tracking", "FileTracker", e)
            return False
    
    def stop_tracking(self):
        """Stop the file change tracking service"""
        try:
            if self.observer:
                self.observer.stop()
                self.observer.join()
                log_info("File change tracking service stopped", "FileTracker")
                
        except Exception as e:
            log_error("Error stopping file change tracking", "FileTracker", e)
    
    def get_recent_changes(self, limit: int = 50) -> list:
        """Get recent changes from the JSON log"""
        try:
            changes_file = Path(self.project_root) / "changes.json"
            if changes_file.exists():
                with open(changes_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("changes", [])[-limit:]
            return []
            
        except Exception as e:
            log_error("Error reading recent changes", "FileTracker", e)
            return []
    
    def get_change_summary(self) -> dict:
        """Get summary of changes"""
        try:
            changes = self.get_recent_changes(1000)  # Get more for summary
            
            summary = {
                "total_changes": len(changes),
                "by_type": {},
                "by_extension": {},
                "recent_files": [],
                "most_active_files": {}
            }
            
            file_counts = {}
            
            for change in changes:
                # Count by type
                event_type = change.get("event_type", "UNKNOWN")
                summary["by_type"][event_type] = summary["by_type"].get(event_type, 0) + 1
                
                # Count by extension
                file_info = change.get("file_info", {})
                ext = file_info.get("extension", "no_extension")
                summary["by_extension"][ext] = summary["by_extension"].get(ext, 0) + 1
                
                # Track file activity
                file_path = change.get("file_path", "")
                file_counts[file_path] = file_counts.get(file_path, 0) + 1
            
            # Get most active files
            summary["most_active_files"] = dict(sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[:10])
            
            # Get recent unique files
            recent_files = []
            seen_files = set()
            for change in reversed(changes[-20:]):  # Last 20 changes
                file_path = change.get("file_path", "")
                if file_path not in seen_files:
                    recent_files.append({
                        "file": file_path,
                        "event": change.get("event_type"),
                        "timestamp": change.get("timestamp")
                    })
                    seen_files.add(file_path)
                    if len(recent_files) >= 10:
                        break
            
            summary["recent_files"] = recent_files
            
            return summary
            
        except Exception as e:
            log_error("Error generating change summary", "FileTracker", e)
            return {}


# Global service instance
_file_change_service = None

def get_file_change_service(project_root: str = None) -> FileChangeService:
    """Get or create the global file change service"""
    global _file_change_service
    
    if _file_change_service is None and project_root:
        _file_change_service = FileChangeService(project_root)
    
    return _file_change_service

def start_file_tracking(project_root: str) -> bool:
    """Start file change tracking for the project"""
    service = get_file_change_service(project_root)
    return service.start_tracking() if service else False

def stop_file_tracking():
    """Stop file change tracking"""
    global _file_change_service
    if _file_change_service:
        _file_change_service.stop_tracking()
