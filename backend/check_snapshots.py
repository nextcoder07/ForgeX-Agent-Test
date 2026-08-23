"""Forensic snapshot checker - shows all snapshot files and their contents."""
import json, os, sys

snap_dir = 'app/services'
print("=== SNAPSHOT FILES ===")
found = False
for f in sorted(os.listdir(snap_dir)):
    if f.startswith('__snapshot'):
        found = True
        path = os.path.join(snap_dir, f)
        size = os.path.getsize(path)
        with open(path) as fp:
            try:
                data = json.load(fp)
            except Exception as e:
                print(f"  {f}: PARSE ERROR {e}")
                continue
        print(f"\nFILE: {f} ({size} bytes), {len(data)} keys")
        for k, v in data.items():
            if isinstance(v, dict):
                spec = v.get('job_spec') or v.get('agent_spec') or v.get('session_spec') or {}
                status = v.get('status', '')
                err = spec.get('error_message') or v.get('error_message') or ''
                print(f"  key={k!r} status={status!r} error={err[:80]!r}")
            else:
                print(f"  key={k!r} -> {type(v).__name__}")

if not found:
    print("No snapshot files found")

print("\n=== SNAPSHOT DIR LISTING ===")
for f in sorted(os.listdir(snap_dir)):
    path = os.path.join(snap_dir, f)
    size = os.path.getsize(path)
    print(f"  {f}: {size} bytes")
