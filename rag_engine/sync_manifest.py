import json, hashlib, os

def compute_hash(filepath):
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        buf = f.read(65536)
        while buf:
            hasher.update(buf)
            buf = f.read(65536)
    return hasher.hexdigest()

raw_dir = 'data/raw'
# Pastikan folder ada agar tidak error
if not os.path.exists(raw_dir):
    print(f"Error: Folder {raw_dir} tidak ditemukan!")
    exit()

manifest = {}
for fname in os.listdir(raw_dir):
    if fname.startswith('.'): continue
    full_path = os.path.join(raw_dir, fname)
    if os.path.isfile(full_path):
        manifest[fname] = {
            'hash': compute_hash(full_path),
            'chunks_generated': -1
        }
        print(f'Registered: {fname} -> {manifest[fname]["hash"][:12]}...')

os.makedirs('storage', exist_ok=True)
with open('storage/ingestion_manifest.json', 'w', encoding='utf-8') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)

print(f'\nManifest tersimpan dengan {len(manifest)} file.')