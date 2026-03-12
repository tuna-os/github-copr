import subprocess
import os
import sys

def clone_package(package_name, dest_dir):
    """
    Clones a package from Fedora Dist-Git via HTTPS.
    """
    pkg_dir = os.path.join(dest_dir, package_name)
    if os.path.exists(pkg_dir):
        print(f"  Directory {pkg_dir} already exists, skipping clone.")
        return True
        
    url = f"https://src.fedoraproject.org/rpms/{package_name}.git"
    command = ["git", "clone", url, pkg_dir, "--depth", "1"]
    try:
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0:
            return True
        else:
            print(f"  Error cloning {package_name}: {result.stderr}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"  Exception cloning {package_name}: {e}", file=sys.stderr)
        return False

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 fetch_rawhide_specs.py <manifest_file> <dest_dir>")
        sys.exit(1)
        
    manifest_file = sys.argv[1]
    dest_dir = sys.argv[2]
    
    if not os.path.exists(manifest_file):
        print(f"Manifest file {manifest_file} not found")
        sys.exit(1)
        
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)
        
    with open(manifest_file, 'r') as f:
        packages = [line.strip() for line in f if line.strip()]
        
    for pkg in packages:
        print(f"Fetching specification for {pkg}...")
        clone_package(pkg, dest_dir)

if __name__ == "__main__":
    main()
