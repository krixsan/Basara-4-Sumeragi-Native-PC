# Diagnostic Data & Privacy Policy

This project values your privacy. We implement a strict **Privacy-by-Design** architecture for crash diagnostics and technical reporting.

---

### 1. Opt-In Telemetry & User Consent
- **Default Behavior:** Set to `Ask each time` (`telemetry_upload=ask` in `basara.ini`).
- **No Silent Uploads:** The application will **never** transmit diagnostic packages in the background without explicit user authorization.
- **Controls:** You can change your preference at any time in the launcher bottom toolbar between:
  - `Ask`: Prompts a confirmation modal dialog on launcher launch if a previous crash occurred.
  - `Never`: Completely disables packaging and network transmission; deletes all crash flags locally.
  - `Always`: Automatically packages crash minidumps for development review without interrupting you.

---

### 2. What Information Is Collected in a Crash Package?
When a crash occurs and you grant consent, the reporter packages:
1. **Crash Minidump (`.dmp`):** Memory register state and thread call stack frames around the fault address.
2. **System Hardware Summary (`manifest.json`):**
   - CPU Model and instruction capabilities
   - Total & Available Physical RAM
   - Windows OS Version & Build number
   - GPU Driver device model (Vulkan adapter)
3. **Engine Log (`basara_anonymized.log`):** The last 1,000 lines of engine debug messages prior to the fault.

---

### 3. Personal Identifiable Information (PII) Scrubbing
Before any crash archive is created or saved to `user/crashes/pending/`, all log text passes through an automated scrubber that redacts:
- **Windows Usernames:** Paths such as `C:\Users\JohnDoe\...` are replaced with `C:\Users\[USER]\...`.
- **Unix/Home Paths:** `/home/username/...` is replaced with `/home/[USER]/...`.
- **Local Network IP Addresses:** IPv4 addresses matching private subnets (`192.168.x.x`, `10.x.x.x`, `172.16-31.x.x`) are replaced with `[REDACTED_IP]`.
- **Physical MAC Addresses:** Network hardware MAC IDs are replaced with `[REDACTED_MAC]`.
- **Passwords, Tokens & Game Save Contents:** Never read, accessed, or included.

---

### 4. Local File Retention
All crash logs and diagnostic dumps remain on your machine in:
```
user/crashes/
├── crash_raw_<TIMESTAMP>.log
└── pending/
    └── crash_package_<TIMESTAMP>.zip
```
You can inspect or delete these files at any time. No background services, daemons, or telemetry background threads remain active when the game or launcher is closed.
