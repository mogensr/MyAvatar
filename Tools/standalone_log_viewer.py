#!/usr/bin/env python3
"""
BackgroundFX Standalone Log Viewer
Run this when you need to debug video processing issues

Usage:
    python standalone_log_viewer.py                    # Web interface on port 8080
    python standalone_log_viewer.py --port 8081        # Custom port
    python standalone_log_viewer.py --export           # Export logs to file
    python standalone_log_viewer.py --filter job_123   # Filter by job ID
"""

import os
import sys
import time
import subprocess
import argparse
import threading
from datetime import datetime, timedelta
from typing import List, Dict
import json

# Try to import web framework
try:
    from flask import Flask, render_template_string, request, jsonify, send_file
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    print("⚠️  Flask not available. Install with: pip install flask")

# Try to import Railway CLI
RAILWAY_AVAILABLE = True
try:
    result = subprocess.run(["railway", "--version"], capture_output=True, text=True, timeout=5)
    if result.returncode != 0:
        RAILWAY_AVAILABLE = False
except:
    RAILWAY_AVAILABLE = False

class BackgroundFXLogViewer:
    def __init__(self):
        self.logs_cache = []
        self.last_update = None
        
    def get_railway_logs(self, lines: int = 100) -> List[Dict]:
        """Get logs from Railway CLI"""
        if not RAILWAY_AVAILABLE:
            return [{"timestamp": datetime.now().isoformat(), "level": "ERROR", 
                    "message": "Railway CLI not available. Install: npm install -g @railway/cli", 
                    "source": "system"}]
        
        try:
            print(f"🔍 Fetching {lines} lines from Railway...")
            result = subprocess.run(
                ["railway", "logs", "--tail", str(lines)],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                parsed_logs = self.parse_railway_logs(result.stdout)
                print(f"✅ Got {len(parsed_logs)} log entries")
                return parsed_logs
            else:
                return [{"timestamp": datetime.now().isoformat(), "level": "ERROR", 
                        "message": f"Railway CLI error: {result.stderr}", "source": "railway"}]
                
        except subprocess.TimeoutExpired:
            return [{"timestamp": datetime.now().isoformat(), "level": "ERROR", 
                    "message": "Railway CLI timeout after 30 seconds", "source": "system"}]
        except Exception as e:
            return [{"timestamp": datetime.now().isoformat(), "level": "ERROR", 
                    "message": f"Railway CLI error: {str(e)}", "source": "system"}]
    
    def parse_railway_logs(self, log_text: str) -> List[Dict]:
        """Parse Railway logs output into structured format"""
        entries = []
        
        for line in log_text.split('\n'):
            if not line.strip():
                continue
                
            try:
                # Try to parse Railway log format
                parts = line.split(' - ', 3)
                if len(parts) >= 4:
                    timestamp_str = parts[0]
                    app_name = parts[1]
                    level = parts[2]
                    message = parts[3]
                    
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    except:
                        timestamp = datetime.now()
                        
                    entries.append({
                        "timestamp": timestamp.isoformat(),
                        "level": level.upper(),
                        "message": message,
                        "app": app_name,
                        "source": "railway"
                    })
                else:
                    # If parsing fails, add as raw message
                    entries.append({
                        "timestamp": datetime.now().isoformat(),
                        "level": "INFO",
                        "message": line,
                        "app": "unknown",
                        "source": "railway"
                    })
                    
            except Exception:
                continue
        
        return sorted(entries, key=lambda x: x["timestamp"], reverse=True)
    
    def filter_logs(self, logs: List[Dict], filters: Dict) -> List[Dict]:
        """Filter logs based on criteria"""
        filtered = logs
        
        # Filter by level
        if filters.get("level") and filters["level"] != "all":
            level_map = {
                "error": ["ERROR", "CRITICAL"],
                "warning": ["WARNING", "WARN"],
                "info": ["INFO"],
                "debug": ["DEBUG"]
            }
            allowed_levels = level_map.get(filters["level"].lower(), [filters["level"].upper()])
            filtered = [entry for entry in filtered if entry.get("level") in allowed_levels]
        
        # Filter by text content
        if filters.get("text"):
            text_filter = filters["text"].lower()
            filtered = [
                entry for entry in filtered 
                if text_filter in entry.get("message", "").lower()
            ]
        
        # Filter by job ID
        if filters.get("job_id"):
            job_filter = filters["job_id"]
            filtered = [
                entry for entry in filtered 
                if job_filter in entry.get("message", "")
            ]
        
        # Filter by time range
        if filters.get("hours"):
            cutoff_time = datetime.now() - timedelta(hours=int(filters["hours"]))
            filtered = [
                entry for entry in filtered
                if datetime.fromisoformat(entry["timestamp"].replace('Z', '+00:00')) > cutoff_time
            ]
        
        return filtered
    
    def export_logs(self, logs: List[Dict], filename: str = None) -> str:
        """Export logs to file"""
        if not filename:
            filename = f"backgroundfx_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        export_content = f"BackgroundFX Logs Export\n"
        export_content += f"Generated: {datetime.now().isoformat()}\n"
        export_content += f"Total Entries: {len(logs)}\n"
        export_content += "=" * 80 + "\n\n"
        
        for entry in logs:
            export_content += f"[{entry['timestamp']}] {entry['level']} - {entry['message']}\n"
        
        with open(filename, 'w') as f:
            f.write(export_content)
        
        print(f"📁 Logs exported to: {filename}")
        return filename

def create_web_interface():
    """Create Flask web interface for log viewing"""
    if not FLASK_AVAILABLE:
        print("❌ Flask not available. Cannot start web interface.")
        return None
    
    app = Flask(__name__)
    log_viewer = BackgroundFXLogViewer()
    
    HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>BackgroundFX Log Viewer</title>
    <style>
        body { font-family: 'Courier New', monospace; margin: 0; padding: 20px; background: #1e1e1e; color: #fff; }
        .header { background: #333; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
        .controls { background: #2d2d2d; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
        .controls input, .controls select, .controls button { 
            margin: 5px; padding: 8px; background: #444; color: #fff; border: 1px solid #666; border-radius: 4px; 
        }
        .log-container { background: #000; padding: 15px; border-radius: 8px; height: 600px; overflow-y: auto; }
        .log-entry { margin: 2px 0; padding: 5px; border-left: 3px solid #666; }
        .log-error { border-left-color: #ff4444; background: rgba(255, 68, 68, 0.1); }
        .log-warning { border-left-color: #ffaa00; background: rgba(255, 170, 0, 0.1); }
        .log-info { border-left-color: #44ff44; background: rgba(68, 255, 68, 0.1); }
        .log-debug { border-left-color: #4444ff; background: rgba(68, 68, 255, 0.1); }
        .timestamp { color: #888; font-size: 0.9em; }
        .level { font-weight: bold; margin: 0 5px; }
        .message { color: #fff; }
        .stats { background: #2d2d2d; padding: 10px; border-radius: 8px; margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎬 BackgroundFX Standalone Log Viewer</h1>
        <p>Debug video processing issues in real-time</p>
    </div>
    
    <div class="controls">
        <input type="text" id="filterText" placeholder="Filter by text..." onkeyup="filterLogs()">
        <input type="text" id="filterJobId" placeholder="Filter by Job ID..." onkeyup="filterLogs()">
        <select id="filterLevel" onchange="filterLogs()">
            <option value="all">All Levels</option>
            <option value="error">Errors Only</option>
            <option value="warning">Warnings</option>
            <option value="info">Info</option>
            <option value="debug">Debug</option>
        </select>
        <select id="lineCount" onchange="refreshLogs()">
            <option value="50">50 lines</option>
            <option value="100" selected>100 lines</option>
            <option value="200">200 lines</option>
            <option value="500">500 lines</option>
        </select>
        <input type="number" id="filterHours" placeholder="Last X hours" min="1" max="24" onchange="filterLogs()">
        <button onclick="refreshLogs()">🔄 Refresh</button>
        <button onclick="exportLogs()">📥 Export</button>
    </div>
    
    <div class="stats" id="stats">
        Loading logs...
    </div>
    
    <div class="log-container" id="logContainer">
        <div>Loading logs...</div>
    </div>
    
    <script>
        function formatLogEntry(entry) {
            const levelClass = `log-${entry.level.toLowerCase()}`;
            const timestamp = new Date(entry.timestamp).toLocaleString();
            
            return `
                <div class="log-entry ${levelClass}">
                    <span class="timestamp">[${timestamp}]</span>
                    <span class="level">${entry.level}</span>
                    <span class="message">${entry.message}</span>
                </div>
            `;
        }
        
        async function refreshLogs() {
            try {
                const lines = document.getElementById('lineCount').value;
                const response = await fetch(`/api/logs?lines=${lines}`);
                const data = await response.json();
                
                if (data.success) {
                    window.allLogs = data.logs;
                    filterLogs();
                    
                    document.getElementById('stats').innerHTML = `
                        📊 Total: ${data.logs.length} | 
                        Updated: ${new Date().toLocaleString()}
                    `;
                } else {
                    document.getElementById('logContainer').innerHTML = `<div class="log-error">Error: ${data.error}</div>`;
                }
            } catch (error) {
                document.getElementById('logContainer').innerHTML = `<div class="log-error">Network Error: ${error.message}</div>`;
            }
        }
        
        function filterLogs() {
            if (!window.allLogs) return;
            
            const level = document.getElementById('filterLevel').value;
            const text = document.getElementById('filterText').value.toLowerCase();
            const jobId = document.getElementById('filterJobId').value;
            const hours = document.getElementById('filterHours').value;
            
            let filtered = window.allLogs;
            
            // Filter by level
            if (level !== 'all') {
                const levelMap = {
                    'error': ['ERROR', 'CRITICAL'],
                    'warning': ['WARNING', 'WARN'],
                    'info': ['INFO'],
                    'debug': ['DEBUG']
                };
                const allowedLevels = levelMap[level] || [level.toUpperCase()];
                filtered = filtered.filter(entry => allowedLevels.includes(entry.level));
            }
            
            // Filter by text
            if (text) {
                filtered = filtered.filter(entry => entry.message.toLowerCase().includes(text));
            }
            
            // Filter by job ID
            if (jobId) {
                filtered = filtered.filter(entry => entry.message.includes(jobId));
            }
            
            // Filter by time
            if (hours) {
                const cutoff = new Date(Date.now() - hours * 60 * 60 * 1000);
                filtered = filtered.filter(entry => new Date(entry.timestamp) > cutoff);
            }
            
            const container = document.getElementById('logContainer');
            container.innerHTML = filtered.map(formatLogEntry).join('');
            
            document.getElementById('stats').innerHTML = `
                📊 Total: ${window.allLogs.length} | Filtered: ${filtered.length} | 
                Updated: ${new Date().toLocaleString()}
            `;
        }
        
        async function exportLogs() {
            try {
                const response = await fetch('/api/export', { method: 'POST' });
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `backgroundfx_logs_${new Date().toISOString().slice(0,16).replace(/:/g,'-')}.txt`;
                a.click();
                window.URL.revokeObjectURL(url);
            } catch (error) {
                alert('Export failed: ' + error.message);
            }
        }
        
        // Initialize
        refreshLogs();
        setInterval(refreshLogs, 30000); // Auto-refresh every 30 seconds
    </script>
</body>
</html>
    '''
    
    @app.route('/')
    def index():
        return HTML_TEMPLATE
    
    @app.route('/api/logs')
    def get_logs():
        try:
            lines = int(request.args.get('lines', 100))
            logs = log_viewer.get_railway_logs(lines)
            
            return jsonify({
                "success": True,
                "logs": logs,
                "count": len(logs),
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/export', methods=['POST'])
    def export_logs():
        try:
            logs = log_viewer.get_railway_logs(1000)  # Get more logs for export
            filename = log_viewer.export_logs(logs)
            return send_file(filename, as_attachment=True)
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    return app

def main():
    parser = argparse.ArgumentParser(description='BackgroundFX Standalone Log Viewer')
    parser.add_argument('--port', type=int, default=8080, help='Web interface port (default: 8080)')
    parser.add_argument('--export', action='store_true', help='Export logs to file and exit')
    parser.add_argument('--filter', type=str, help='Filter logs by text/job ID')
    parser.add_argument('--level', choices=['error', 'warning', 'info', 'debug', 'all'], 
                       default='all', help='Filter by log level')
    parser.add_argument('--lines', type=int, default=100, help='Number of log lines to fetch')
    parser.add_argument('--hours', type=int, help='Filter logs from last X hours')
    
    args = parser.parse_args()
    
    print("🎬 BackgroundFX Standalone Log Viewer")
    print("=" * 50)
    
    log_viewer = BackgroundFXLogViewer()
    
    if args.export:
        # Export mode
        print(f"📥 Exporting {args.lines} log lines...")
        logs = log_viewer.get_railway_logs(args.lines)
        
        # Apply filters
        filters = {
            "level": args.level,
            "text": args.filter,
            "hours": args.hours
        }
        filtered_logs = log_viewer.filter_logs(logs, filters)
        
        filename = log_viewer.export_logs(filtered_logs)
        print(f"✅ Exported {len(filtered_logs)} filtered logs to {filename}")
        return
    
    # Web interface mode
    if not FLASK_AVAILABLE:
        print("❌ Web interface requires Flask. Install with: pip install flask")
        print("💡 Use --export flag to export logs without web interface")
        return
    
    app = create_web_interface()
    if app:
        print(f"🌐 Starting web interface on http://localhost:{args.port}")
        print("🔍 Use this for real-time log debugging")
        print("📊 Auto-refreshes every 30 seconds")
        print("💡 Ctrl+C to stop")
        
        try:
            app.run(host='0.0.0.0', port=args.port, debug=False)
        except KeyboardInterrupt:
            print("\n👋 Log viewer stopped")

if __name__ == "__main__":
    main()
