# OFSAA Installation — Steps Quick Reference

---

## BD Pack Only

```
 1. Create oracle user & oinstall group
 2. Create mount point /u01
 3. Install KSH & Git
 4. Create .profile
 5. Install Java & update profile
 6. Create OFSAA directory structure
 7. Check Oracle client & update profile
 8. Download installer kit, set permissions, run envCheck
 9. Apply config XMLs/properties → run osc.sh (schema creator)
10. Run setup.sh SILENT
      └─ RAM fail? → drop caches → retry setup.sh once
11. Take BD backup (app tar + DB schema dump)
      └─ Filename: OFSAA_BKP_BD_YYYYMMDD_HHMMSS.tar.gz
```

---

## ECM Only (BD already installed)

```
 1. Verify BD backups exist (auto-backup if missing)
 
 2. Download & extract ECM installer kit
 3. Set ECM kit permissions
 4. Apply ECM config files (schema XML, properties, AAI config)
 5. Run ECM osc.sh (schema creator)
      └─ Fail? → kill Java → restore BD state → stop
 6. Run ECM setup.sh SILENT
      └─ RAM fail? → drop caches → retry setup.sh once
      └─ Still fail? → kill Java → restore BD state → stop
 7. Take ECM success backup
      └─ Filename: OFSAA_BKP_ECM_YYYYMMDD_HHMMSS.tar.gz
 8. Clear BD checkpoint
```

---

## BD + ECM Together

```
── BD PACK ──
 1. Create oracle user & oinstall group
 2. Create mount point /u01
 3. Install KSH & Git
 4. Create .profile
 5. Install Java & update profile
 6. Create OFSAA directory structure
 7. Check Oracle client & update profile
 8. Download installer kit, set permissions, run envCheck
 9. Apply config XMLs/properties → run osc.sh
10. Run setup.sh SILENT
      └─ RAM fail? → drop caches → retry once
11. Take BD backup (app tar + DB dump)

── ECM PACK ──
12. Verify BD backups exist
13. Download & extract ECM installer kit
14. Set ECM kit permissions
15. Apply ECM config files
16. Run ECM osc.sh
      └─ Fail? → restore to BD state → stop
17. Run ECM setup.sh SILENT
      └─ RAM fail? → drop caches → retry once
      └─ Still fail? → restore to BD state → stop
18. Take ECM success backup
19. Clear BD checkpoint
20. Done ✓
```

---

## Recovery Summary

| Failure Point | What Happens |
|---------------|-------------|
| BD osc.sh fails | Kill Java → drop schemas → rm OFSAA → full retry needed |
| BD setup.sh RAM fail | Drop caches → auto-retry setup.sh once |
| BD setup.sh other fail | Kill Java → cleanup → full retry needed |
| ECM osc.sh fails | Kill Java → restore BD backup (app + DB) → retry ECM with `resume_from_checkpoint` |
| ECM setup.sh RAM fail | Drop caches → auto-retry setup.sh once |
| ECM setup.sh other fail | Kill Java → restore BD backup → retry ECM with `resume_from_checkpoint` |
