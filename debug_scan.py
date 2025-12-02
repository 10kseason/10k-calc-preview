import os

def scan_files(target_dirs):
    """Generator that yields file paths from target directories."""
    extensions = {'.bms', '.bme', '.bml', '.osu'}
    print(f"Scanning directories: {target_dirs}")
    for root_dir in target_dirs:
        if not os.path.exists(root_dir):
            print(f"Directory not found: {root_dir}")
            continue
            
        print(f"Walking: {root_dir}")
        count = 0
        for root, dirs, files in os.walk(root_dir):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in extensions:
                    # print(f"Found: {os.path.join(root, file)}")
                    count += 1
        print(f"Found {count} files in {root_dir}")

if __name__ == "__main__":
    target_dirs = [
        r"d:\계산기\패턴 모음2(GCS)",
        r"d:\계산기\10k revive", # Assuming this exists based on user prompt
        r"d:\계산기\10k2s"      # Assuming this exists based on user prompt
    ]
    scan_files(target_dirs)
