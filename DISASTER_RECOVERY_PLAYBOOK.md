# 🛡️ MyAvatar Disaster Recovery Playbook

## 🚨 EMERGENCY PROCEDURES

### **IMMEDIATE RESPONSE (0-5 minutes)**

1. **STOP ALL DEPLOYMENTS**
   ```bash
   # If using Railway
   railway down
   
   # If using other platforms, stop deployments immediately
   ```

2. **ASSESS THE DAMAGE**
   ```bash
   # Check current state
   git status
   git log --oneline -10
   
   # Check if files are missing/corrupted
   ls -la main.py requirements.txt app/ templates/
   ```

3. **IDENTIFY LAST KNOWN GOOD STATE**
   ```bash
   # Find recent working commits
   git log --oneline --since="7 days ago"
   
   # Check GitHub Actions backup artifacts
   # Go to: https://github.com/YOUR_REPO/actions
   ```

### **RECOVERY OPTIONS (5-15 minutes)**

#### **OPTION 1: Git-Based Recovery (RECOMMENDED)**
```bash
# Find the last working commit (like bc58281)
git log --oneline -20

# Reset to working commit
git reset --hard WORKING_COMMIT_HASH

# Force push to restore production
git push origin main --force
```

#### **OPTION 2: GitHub Backup Artifact Recovery**
```bash
# Download latest backup from GitHub Actions
# Extract the backup archive
tar -xzf MyAvatar_BACKUP_*.tar.gz

# Copy files back
cp -r backup_*/app/ ./app/
cp -r backup_*/templates/ ./templates/
cp backup_*/main.py ./main.py
cp backup_*/requirements.txt ./requirements.txt

# Commit and push
git add .
git commit -m "🛡️ Emergency restore from backup artifact"
git push origin main
```

#### **OPTION 3: Nuclear Reset (LAST RESORT)**
```bash
# Clone fresh from GitHub
cd ..
git clone https://github.com/YOUR_USERNAME/MyAvatar.git MyAvatar_FRESH
cd MyAvatar_FRESH

# Find working commit and reset
git reset --hard WORKING_COMMIT_HASH
git push origin main --force
```

### **VERIFICATION CHECKLIST (15-20 minutes)**

- [ ] **Files Exist**: main.py, requirements.txt, app/, templates/
- [ ] **Python Syntax**: `python -m py_compile main.py`
- [ ] **Import Test**: `python -c "import main; print('SUCCESS')"`
- [ ] **Requirements Valid**: Check requirements.txt is not empty
- [ ] **Git Status Clean**: `git status` shows clean working tree
- [ ] **Production Deploy**: Railway/platform rebuilding successfully
- [ ] **Application Running**: Test login, dashboard, key features

### **POST-RECOVERY ACTIONS (20-30 minutes)**

1. **Document the Incident**
   ```bash
   # Create incident report
   echo "# Disaster Recovery Report - $(date)" > INCIDENT_REPORT_$(date +%Y%m%d).md
   echo "## What Happened:" >> INCIDENT_REPORT_$(date +%Y%m%d).md
   echo "## Recovery Method Used:" >> INCIDENT_REPORT_$(date +%Y%m%d).md
   echo "## Lessons Learned:" >> INCIDENT_REPORT_$(date +%Y%m%d).md
   ```

2. **Trigger Fresh Backup**
   ```bash
   # Manual backup trigger
   gh workflow run disaster-proof-backup.yml
   ```

3. **Test Recovery System**
   ```bash
   # Run disaster recovery drill
   gh workflow run disaster-recovery-drill.yml
   ```

---

## 🔧 PREVENTION MEASURES

### **Daily Habits**
- ✅ Commit frequently with meaningful messages
- ✅ Push to GitHub after each working session
- ✅ Never work directly on production without backup
- ✅ Test changes in development first

### **Weekly Habits**
- ✅ Review GitHub Actions backup status
- ✅ Verify backup artifacts are being created
- ✅ Check disaster recovery drill results
- ✅ Update documentation if needed

### **Monthly Habits**
- ✅ Run manual disaster recovery drill
- ✅ Review and update recovery procedures
- ✅ Test all recovery options end-to-end
- ✅ Archive old backup artifacts

---

## 📞 EMERGENCY CONTACTS

### **Automated Systems**
- **GitHub Actions**: Automatic backups and alerts
- **Railway**: Auto-deployment from main branch
- **Monitoring**: Application health checks

### **Manual Triggers**
```bash
# Trigger emergency backup
gh workflow run disaster-proof-backup.yml -f backup_type=emergency

# Run recovery drill
gh workflow run disaster-recovery-drill.yml -f test_type=emergency

# Check backup status
gh run list --workflow=disaster-proof-backup.yml
```

---

## 🎯 COMMIT HASH REFERENCE

**KNOWN GOOD COMMITS:**
- `bc58281` - Enhanced avatar diagnostic system (Aug 3, 2025)
- `[ADD_MORE_AS_NEEDED]`

**RECOVERY COMMANDS:**
```bash
# Restore to bc58281 (known working)
git reset --hard bc58281
git push origin main --force

# Alternative: checkout specific commit
git checkout bc58281
git checkout -b recovery-branch
git push origin recovery-branch
```

---

## ⚠️ WHAT NOT TO DO

❌ **NEVER** copy files from old backups without checking dates  
❌ **NEVER** overwrite working code with untested backups  
❌ **NEVER** skip verification steps after recovery  
❌ **NEVER** deploy to production without testing locally first  
❌ **NEVER** ignore GitHub Actions backup failures  

---

## ✅ SUCCESS CRITERIA

**Recovery is complete when:**
- ✅ Application starts without errors
- ✅ All critical routes work (login, dashboard, video creation)
- ✅ Database connections successful
- ✅ Admin authentication functional
- ✅ No import or dependency errors
- ✅ Production deployment successful

---

*Last Updated: $(date)*  
*Next Review: Monthly on 1st*
