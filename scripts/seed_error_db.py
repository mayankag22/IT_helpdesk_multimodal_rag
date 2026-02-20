"""
scripts/seed_error_db.py
Seeds the SQLite error-code database with representative sample data.
Run this once before starting the application.

Usage:
    python scripts/seed_error_db.py
    python scripts/seed_error_db.py --db /custom/path/error_codes.db
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.mcp_server.tools.error_lookup import ErrorLookup


SAMPLE_ERRORS = [
    # ── Network / PCIe ────────────────────────────────────────────────────────
    {
        "code":        "0x4F",
        "category":    "PCIe / Network",
        "description": "PCIe link negotiation failure",
        "root_cause":  "Network adapter not properly seated or BIOS PCIe config mismatch.",
        "fix_steps":   "1. Power off. 2. Reseat the network card firmly. 3. Enter BIOS → PCIe slot → set to Auto/Gen 3. 4. Power on and re-test.",
        "severity":    "HIGH",
        "references":  "Intel NIC Troubleshooting Guide §4.2",
    },
    {
        "code":        "ERR_LINK_DOWN",
        "category":    "Network",
        "description": "Physical network link is down",
        "root_cause":  "Cable disconnected, switch port down, or NIC driver failure.",
        "fix_steps":   "1. Check cable connections at both ends. 2. Try a known-good cable. 3. Verify switch port is active. 4. Reload NIC driver: modprobe -r <driver> && modprobe <driver>.",
        "severity":    "HIGH",
        "references":  "",
    },
    # ── Storage ───────────────────────────────────────────────────────────────
    {
        "code":        "DISKFULL",
        "category":    "Storage",
        "description": "Disk volume is full",
        "root_cause":  "Available disk space exhausted; writes blocked.",
        "fix_steps":   "1. Run df -h to identify full volume. 2. Find large files: du -sh /* | sort -rh | head -20. 3. Archive or delete old logs. 4. Extend volume if on LVM.",
        "severity":    "MEDIUM",
        "references":  "",
    },
    {
        "code":        "0xC000021A",
        "category":    "Windows Boot",
        "description": "Windows critical system process failed (BSOD)",
        "root_cause":  "Corrupted system files, bad driver, or recent Windows Update issue.",
        "fix_steps":   "1. Boot into Safe Mode. 2. Run sfc /scannow. 3. Run DISM /Online /Cleanup-Image /RestoreHealth. 4. Check Event Viewer for faulting process. 5. Roll back recent updates if applicable.",
        "severity":    "CRITICAL",
        "references":  "Microsoft KB 4015583",
    },
    # ── HTTP ─────────────────────────────────────────────────────────────────
    {
        "code":        "HTTP 502",
        "category":    "HTTP / Web",
        "description": "Bad Gateway — upstream server returned invalid response",
        "root_cause":  "Backend service down, timeout, or misconfigured proxy.",
        "fix_steps":   "1. Check upstream service health. 2. Review nginx/haproxy logs. 3. Increase proxy timeout if latency is the cause. 4. Restart backend service.",
        "severity":    "HIGH",
        "references":  "",
    },
    {
        "code":        "HTTP 503",
        "category":    "HTTP / Web",
        "description": "Service Unavailable",
        "root_cause":  "Server overloaded or in maintenance mode.",
        "fix_steps":   "1. Check server CPU/memory. 2. Review application logs. 3. Scale up or add replicas. 4. Disable maintenance mode if set.",
        "severity":    "HIGH",
        "references":  "",
    },
    # ── Memory ───────────────────────────────────────────────────────────────
    {
        "code":        "ERR_OUT_OF_MEMORY",
        "category":    "Memory",
        "description": "Process ran out of memory (OOM)",
        "root_cause":  "Application memory leak or insufficient RAM for workload.",
        "fix_steps":   "1. Check free memory: free -h. 2. Identify top consumers: ps aux --sort=-%mem | head. 3. Restart leaking process. 4. Add swap or upgrade RAM if persistent.",
        "severity":    "HIGH",
        "references":  "",
    },
    # ── Thermal ──────────────────────────────────────────────────────────────
    {
        "code":        "THERMAL_SHUTDOWN",
        "category":    "Hardware / Thermal",
        "description": "System shut down due to overheating",
        "root_cause":  "Blocked airflow, failed fan, dried thermal paste, or ambient temperature too high.",
        "fix_steps":   "1. Check CPU/GPU temps with sensors or HWiNFO. 2. Clean dust from vents and heatsinks. 3. Verify all fans spin at POST. 4. Reapply thermal paste if >3 years old.",
        "severity":    "CRITICAL",
        "references":  "",
    },
]

SAMPLE_SECTIONS = [
    {
        "section_id": "NIC-LED-AMBER",
        "title":      "Network Card LED Indicator States",
        "content":    "Amber blinking at ~1 Hz: PCIe link negotiation in progress or failed. Solid amber: hardware fault detected. Green solid: link established at 1 Gbps. Green blinking: active data transfer. No light: no power or physical cable disconnected.",
        "device":     "Generic NIC",
    },
    {
        "section_id": "POST-CODES",
        "title":      "POST Diagnostic Code Reference",
        "content":    "0x00-0x0F: CPU initialisation. 0x10-0x1F: Memory test. 0x20-0x3F: PCI bus enumeration. 0x40-0x4F: PCIe device initialisation — 0x4F specifically indicates PCIe link failure. 0x50-0x5F: USB initialisation. 0x60+: Boot device search.",
        "device":     "Generic x86 Mainboard",
    },
    {
        "section_id": "BIOS-PCIE",
        "title":      "BIOS PCIe Slot Configuration",
        "content":    "Navigate to: Advanced → PCIe Configuration → PCIe Slot Speed. Set to 'Auto' for automatic negotiation. If a device fails at Gen4, try Gen3. Bifurcation settings affect x16 slots split into x8/x8. Always save and exit before testing.",
        "device":     "Generic UEFI BIOS",
    },
]


def main():
    parser = argparse.ArgumentParser(description="Seed the MCP error code database.")
    parser.add_argument("--db", default="services/mcp_server/data/error_codes.db",
                        help="Path to the SQLite database file.")
    args = parser.parse_args()

    store = ErrorLookup(db_path=args.db)

    print(f"Seeding error codes into: {args.db}")
    for e in SAMPLE_ERRORS:
        store.seed_error(**e)
        print(f"  ✓ {e['code']:30s}  [{e['severity']}]")

    print("\nSeeding manual sections:")
    for s in SAMPLE_SECTIONS:
        store.seed_section(**s)
        print(f"  ✓ {s['section_id']}")

    print(f"\nDone. {len(SAMPLE_ERRORS)} error codes, {len(SAMPLE_SECTIONS)} manual sections seeded.")


if __name__ == "__main__":
    main()
