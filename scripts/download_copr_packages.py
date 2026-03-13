import subprocess
import os
import sys
import re

def get_latest_successful_build(repo, package_name):
    """
    Returns the latest successful build ID for a package in a repo.
    """
    command = ["copr-cli", "list-builds", repo]
    try:
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            return None
        
        # Output is like:
        # ID        Package    Status
        # 10208168  selinux-policy  succeeded
        lines = result.stdout.splitlines()
        for line in lines:
            parts = line.split()
            if len(parts) >= 3:
                b_id, b_pkg, b_status = parts[0], parts[1], parts[2]
                if b_pkg == package_name and b_status == "succeeded":
                    return b_id
        return None
    except Exception:
        return None

def download_srpm(build_id, dest_dir):
    """
    Downloads a build and keeps only the .src.rpm.
    """
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)
        
    # We use epel-10-x86_64 as the chroot to find the SRPM
    command = ["copr-cli", "download-build", "--chroot", "epel-10-x86_64", "--dest", dest_dir, build_id]
    try:
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error downloading build {build_id}: {result.stderr}", file=sys.stderr)
            return False
            
        # Clean up everything except .src.rpm
        # Files are in dest_dir/epel-10-x86_64/<build_id>-<pkg_name>/...
        # We want to move the .src.rpm to dest_dir and delete the rest.
        
        found_srpm = False
        for root, dirs, files in os.walk(dest_dir):
            for file in files:
                if file.endswith(".src.rpm"):
                    src_path = os.path.join(root, file)
                    dest_path = os.path.join(dest_dir, file)
                    os.rename(src_path, dest_path)
                    found_srpm = True
                    break
            if found_srpm:
                break
        
        # Delete the chroot directory
        chroot_dir = os.path.join(dest_dir, "epel-10-x86_64")
        if os.path.exists(chroot_dir):
            import shutil
            shutil.rmtree(chroot_dir)
            
        return found_srpm
    except Exception as e:
        print(f"Exception downloading build {build_id}: {e}", file=sys.stderr)
        return False

def main():
    if len(sys.argv) < 4:
        print("Usage: python3 download_copr_packages.py <repo> <manifest_file> <dest_dir>")
        sys.exit(1)
    
    repo = sys.argv[1]
    manifest_file = sys.argv[2]
    dest_dir = sys.argv[3]
    
    if not os.path.exists(manifest_file):
        print(f"Manifest file {manifest_file} not found")
        sys.exit(1)
        
    with open(manifest_file, 'r') as f:
        packages = [line.strip() for line in f if line.strip()]
        
    for pkg in packages:
        print(f"Processing {pkg}...")
        build_id = get_latest_successful_build(repo, pkg)
        if build_id:
            print(f"  Found build {build_id}. Downloading SRPM...")
            if download_srpm(build_id, dest_dir):
                print(f"  Successfully downloaded SRPM for {pkg}.")
            else:
                print(f"  Failed to download SRPM for {pkg}.")
        else:
            print(f"  No successful build found for {pkg}.")

if __name__ == "__main__":
    main()
