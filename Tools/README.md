# 🛠️ MyAvatar Development Tools

This directory contains debugging and maintenance tools for the MyAvatar project.

## 📋 Available Tools

### 🎬 `standalone_log_viewer.py` - BackgroundFX Log Debugging

Real-time log viewer for debugging video processing issues.

#### **Quick Start**
```bash
# Start web interface (recommended)
python tools/standalone_log_viewer.py

# Open browser to: http://localhost:8080
```

#### **Usage Examples**

**🌐 Web Interface (Interactive)**
```bash
# Default web interface
python tools/standalone_log_viewer.py

# Custom port
python tools/standalone_log_viewer.py --port 8081

# Access from browser: http://localhost:8080
```

**📁 Export Logs (Command Line)**
```bash
# Export all recent logs
python tools/standalone_log_viewer.py --export

# Export only errors from last 2 hours
python tools/standalone_log_viewer.py --export --level error --hours 2

# Export logs containing specific job ID
python tools/standalone_log_viewer.py --export --filter "hf_1234567_1"

# Export more lines
python tools/standalone_log_viewer.py --export --lines 500
```

**🔍 Filter Examples**
```bash
# Only error logs
python tools/standalone_log_viewer.py --level error

# Filter by text
python tools/standalone_log_viewer.py --filter "429 Too Many Requests"

# Last 4 hours only
python tools/standalone_log_viewer.py --hours 4
```

#### **Web Interface Features**

- ✅ **Real-time updates** every 30 seconds
- ✅ **Live filtering** by level, text, job ID, time
- ✅ **Color-coded logs** (errors=red, warnings=yellow, etc.)
- ✅ **Export functionality** built-in
- ✅ **Mobile-friendly** interface

#### **Common Debugging Scenarios**

**🚨 Video Processing Stuck**
```bash
# Look for specific job
python tools/standalone_log_viewer.py --filter "hf_1234567_1"

# Check for rate limiting errors
python tools/standalone_log_viewer.py --filter "429"
```

**💥 Processing Failures**
```bash
# Show only errors from last hour
python tools/standalone_log_viewer.py --level error --hours 1

# Export for sharing with team
python tools/standalone_log_viewer.py --export --level error --hours 6
```

**🔍 General Health Check**
```bash
# Web interface for overall monitoring
python tools/standalone_log_viewer.py
# Then filter in browser as needed
```

#### **Prerequisites**

**Required:**
- Railway CLI installed (`npm install -g @railway/cli`)
- Python 3.7+

**Optional (for web interface):**
- Flask (`pip install flask`)

If Flask not available, use `--export` mode only.

#### **Troubleshooting**

**❌ "Railway CLI not available"**
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login
```

**❌ "Flask not available"**
```bash
# Option 1: Install Flask
pip install flask

# Option 2: Use export mode only
python tools/standalone_log_viewer.py --export
```

**❌ "Permission denied"**
```bash
# Make executable
chmod +x tools/standalone_log_viewer.py
```

---

## 🔮 Future Tools (Coming Soon)

### `db_maintenance.py`
- Database health checks
- Table cleanup utilities
- User data migrations

### `health_checker.py`
- System status monitoring
- API endpoint testing
- Service dependency checks

### `performance_analyzer.py`
- Video processing performance metrics
- Resource usage tracking
- Bottleneck identification

---

## 💡 Usage Tips

**🎯 When to Use Each Tool:**

| Scenario | Tool | Command |
|----------|------|---------|
| Video processing stuck | Log Viewer (Web) | `python tools/standalone_log_viewer.py` |
| Share logs with team | Log Viewer (Export) | `python tools/standalone_log_viewer.py --export --hours 2` |
| Monitor real-time issues | Log Viewer (Web) | Keep browser open on localhost:8080 |
| Debug specific job | Log Viewer (Filter) | `python tools/standalone_log_viewer.py --filter "job_id"` |

**🔄 Development Workflow:**

1. **Issue reported** → Start log viewer web interface
2. **Reproduce issue** → Filter logs in real-time
3. **Identify problem** → Export relevant logs
4. **Fix issue** → Monitor logs to verify fix
5. **Close tool** → No impact on production

**🚀 Pro Tips:**

- **Bookmark** `http://localhost:8080` for quick access
- **Keep log viewer open** during development/testing
- **Export logs** before major deployments
- **Filter by user ID** to debug specific user issues
- **Use time filters** to focus on recent problems

---

## 📞 Support

**For tool issues:**
- Check Railway CLI is logged in: `railway whoami`
- Verify Python version: `python --version` (need 3.7+)
- Check file permissions: `ls -la tools/`

**For video processing issues:**
- Use log viewer to identify specific error messages
- Check rate limiting status (429 errors)
- Verify HF Space connectivity
- Monitor job completion times

---

*Last updated: {current_date}*
*Tools version: 1.0.0*