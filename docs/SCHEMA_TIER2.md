# Tier 2 JSON Schema (v1.0.0)

Focus: supply-chain & locality risk signals.
Stable keys:

```json
{
  "schema_version": "1.0.0",
  "tier": 2,
  "timestamp_utc": "<ISO 8601>",
  "target_rootfs": "/ or <path>",
  "repos": {
    "apt": [
      {"file": "/etc/apt/sources.list", "lines": ["deb http://...", "..."]}
    ],
    "yum_dnf": [
      {"file": "/etc/yum.repos.d/rocky.repo", "content": "[baseos]\nname=...\nbaseurl=..."}
    ]
  },
  "path_shadowing": {
    "ls": ["/bin/ls", "/usr/bin/ls"]
  },
  "manual_areas": [
    {"dir": "/usr/local", "entries": ["/usr/local/bin", "/usr/local/sbin"]},
    {"dir": "/opt", "entries": ["/opt/app"]}
  ]
}
```

### Pacman
```json
"repos": {
  "apt": [],
  "yum_dnf": [],
  "pacman": [
    {"file": "/etc/pacman.conf", "content": "[options]\n..."},
    {"file": "/etc/pacman.d/mirrorlist", "servers": ["https://mirror1/$repo/os/$arch"]}
  ]
}
```
