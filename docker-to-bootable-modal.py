import modal
import subprocess
import os
import tempfile
import shutil
from pathlib import Path
import logging

# Define the Modal app
app = modal.App("docker-to-bootable-img")

# Create a custom image with all necessary tools
docker_converter_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install([
        "docker.io",
        "qemu-utils", 
        "extlinux", 
        "syslinux-common",
        "fdisk",
        "parted",
        "e2fsprogs",
        "dosfstools",
        "libguestfs-tools",
        "guestfs-tools",
        "mount"
    ])
    .run_commands([
        "systemctl enable docker || true",
        "mkdir -p /tmp/docker-conversion"
    ])
    .pip_install([
        "docker",
        "requests"
    ])
)

@app.function(
    image=docker_converter_image,
    cpu=4,
    memory=8192,
    timeout=3600,  # 1 hour timeout for large conversions
    volumes={
        "/tmp/conversion": modal.Volume.from_name("docker-conversion-volume", create_if_missing=True)
    },
    allow_network_access=True
)
def convert_docker_to_bootable_img(
    docker_image: str,
    output_filename: str = "bootable_system.img",
    disk_size_mb: int = 2048,
    filesystem_type: str = "ext4"
) -> dict:
    """
    Convert a Docker image/container to a bootable .img file
    
    Args:
        docker_image: Docker image name (e.g., "alpine:latest", "ubuntu:20.04")
        output_filename: Name of the output .img file
        disk_size_mb: Size of the bootable disk image in MB
        filesystem_type: Filesystem type (ext4, ext3, ext2)
    
    Returns:
        dict: Contains status, file path, and conversion details
    """
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    try:
        # Step 1: Start Docker daemon
        logger.info("Starting Docker daemon...")
        subprocess.run(["dockerd", "--host=unix:///var/run/docker.sock"], 
                      check=False, timeout=10, capture_output=True)
        
        # Step 2: Pull the Docker image
        logger.info(f"Pulling Docker image: {docker_image}")
        result = subprocess.run(
            ["docker", "pull", docker_image], 
            capture_output=True, text=True, check=True
        )
        
        # Step 3: Create a container from the image  
        logger.info("Creating container from image...")
        container_result = subprocess.run(
            ["docker", "create", docker_image], 
            capture_output=True, text=True, check=True
        )
        container_id = container_result.stdout.strip()
        
        # Step 4: Export container filesystem to tar
        tar_path = f"/tmp/conversion/{docker_image.replace(':', '_').replace('/', '_')}.tar"
        logger.info(f"Exporting container filesystem to {tar_path}")
        with open(tar_path, "wb") as tar_file:
            subprocess.run(
                ["docker", "export", container_id], 
                stdout=tar_file, check=True
            )
        
        # Step 5: Create empty disk image
        img_path = f"/tmp/conversion/{output_filename}"
        logger.info(f"Creating {disk_size_mb}MB disk image: {img_path}")
        subprocess.run([
            "dd", "if=/dev/zero", f"of={img_path}", 
            f"bs=1M", f"count={disk_size_mb}"
        ], check=True, capture_output=True)
        
        # Step 6: Create partition table and filesystem
        logger.info("Creating partition table...")
        fdisk_commands = f"""o
n
p
1


a
1
w
"""
        subprocess.run(
            ["fdisk", img_path], 
            input=fdisk_commands, text=True, check=True, capture_output=True
        )
        
        # Step 7: Set up loop device
        logger.info("Setting up loop device...")
        loop_result = subprocess.run(
            ["losetup", "-P", "--find", "--show", img_path],
            capture_output=True, text=True, check=True
        )
        loop_device = loop_result.stdout.strip()
        partition_device = f"{loop_device}p1"
        
        try:
            # Step 8: Create filesystem on partition
            logger.info(f"Creating {filesystem_type} filesystem...")
            subprocess.run([
                f"mkfs.{filesystem_type}", partition_device
            ], check=True, capture_output=True)
            
            # Step 9: Mount the partition
            mount_point = "/tmp/conversion/mnt"
            os.makedirs(mount_point, exist_ok=True)
            subprocess.run([
                "mount", partition_device, mount_point
            ], check=True)
            
            try:
                # Step 10: Extract container filesystem
                logger.info("Extracting container filesystem to mounted partition...")
                subprocess.run([
                    "tar", "-xf", tar_path, "-C", mount_point
                ], check=True)
                
                # Step 11: Install kernel (for Debian/Ubuntu-based images)
                logger.info("Installing kernel and bootloader components...")
                
                # Check if it's a Debian/Ubuntu-based system
                if os.path.exists(f"{mount_point}/etc/apt/sources.list") or os.path.exists(f"{mount_point}/etc/debian_version"):
                    # Set up chroot environment
                    subprocess.run(["mount", "--bind", "/dev", f"{mount_point}/dev"], check=False)
                    subprocess.run(["mount", "--bind", "/proc", f"{mount_point}/proc"], check=False)
                    subprocess.run(["mount", "--bind", "/sys", f"{mount_point}/sys"], check=False)
                    
                    # Install kernel in chroot
                    chroot_script = f"""#!/bin/bash
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y linux-image-generic systemd-sysv
apt-get install -y extlinux syslinux-common
"""
                    script_path = f"{mount_point}/install_kernel.sh"
                    with open(script_path, "w") as f:
                        f.write(chroot_script)
                    os.chmod(script_path, 0o755)
                    
                    subprocess.run([
                        "chroot", mount_point, "/install_kernel.sh"
                    ], check=False, capture_output=True)
                
                # Step 12: Install bootloader
                logger.info("Installing EXTLINUX bootloader...")
                boot_dir = f"{mount_point}/boot"
                os.makedirs(f"{boot_dir}/extlinux", exist_ok=True)
                
                # Install EXTLINUX
                subprocess.run([
                    "extlinux", "--install", f"{boot_dir}/extlinux"
                ], check=True, capture_output=True)
                
                # Create bootloader configuration
                extlinux_conf = f"""DEFAULT linux
TIMEOUT 30
PROMPT 1

LABEL linux
    MENU LABEL Boot Linux
    LINUX /vmlinuz
    INITRD /initrd.img
    APPEND root=/dev/sda1 rw console=tty0 console=ttyS0,115200n8
"""
                
                config_path = f"{boot_dir}/extlinux/extlinux.conf"
                with open(config_path, "w") as f:
                    f.write(extlinux_conf)
                
                # Step 13: Create basic init system (if systemd not available)
                if not os.path.exists(f"{mount_point}/sbin/init"):
                    logger.info("Creating basic init script...")
                    init_script = """#!/bin/sh
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev
echo "Container-based Linux system booted successfully!"
/bin/sh
"""
                    with open(f"{mount_point}/sbin/init", "w") as f:
                        f.write(init_script)
                    os.chmod(f"{mount_point}/sbin/init", 0o755)
                
            finally:
                # Cleanup: Unmount filesystems
                logger.info("Unmounting filesystems...")
                subprocess.run(["umount", f"{mount_point}/dev"], check=False, capture_output=True)
                subprocess.run(["umount", f"{mount_point}/proc"], check=False, capture_output=True) 
                subprocess.run(["umount", f"{mount_point}/sys"], check=False, capture_output=True)
                subprocess.run(["umount", mount_point], check=False, capture_output=True)
                
        finally:
            # Cleanup: Detach loop device
            subprocess.run(["losetup", "-d", loop_device], check=False, capture_output=True)
        
        # Step 14: Install MBR bootloader
        logger.info("Installing MBR bootloader...")
        subprocess.run([
            "dd", "bs=440", "count=1", "conv=notrunc",
            "if=/usr/lib/syslinux/mbr.bin", f"of={img_path}"
        ], check=True, capture_output=True)
        
        # Step 15: Cleanup temporary files
        if os.path.exists(tar_path):
            os.remove(tar_path)
        
        # Clean up Docker container
        subprocess.run(["docker", "rm", container_id], check=False, capture_output=True)
        
        # Get file size
        file_size = os.path.getsize(img_path)
        
        logger.info(f"Conversion completed successfully! Output: {img_path}")
        
        return {
            "status": "success",
            "output_file": img_path,
            "file_size_mb": file_size // (1024 * 1024),
            "docker_image": docker_image,
            "disk_size_mb": disk_size_mb,
            "filesystem_type": filesystem_type,
            "message": f"Successfully converted {docker_image} to bootable {output_filename}"
        }
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {e.cmd}")
        logger.error(f"Error output: {e.stderr}")
        return {
            "status": "error",
            "error": str(e),
            "command": e.cmd,
            "stderr": e.stderr if hasattr(e, 'stderr') else None
        }
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {
            "status": "error", 
            "error": str(e)
        }

@app.function(
    image=docker_converter_image,
    cpu=2,
    memory=4096
)
def list_conversion_files() -> list:
    """List all converted .img files in the volume"""
    conversion_dir = "/tmp/conversion"
    if os.path.exists(conversion_dir):
        files = []
        for file in os.listdir(conversion_dir):
            if file.endswith('.img'):
                file_path = os.path.join(conversion_dir, file)
                file_size = os.path.getsize(file_path)
                files.append({
                    "filename": file,
                    "path": file_path,
                    "size_mb": file_size // (1024 * 1024)
                })
        return files
    return []

@app.function(
    image=docker_converter_image,
    cpu=1,
    memory=2048
)
def cleanup_conversion_files() -> dict:
    """Clean up all conversion files from the volume"""
    conversion_dir = "/tmp/conversion"
    if os.path.exists(conversion_dir):
        shutil.rmtree(conversion_dir)
        os.makedirs(conversion_dir, exist_ok=True)
        return {"status": "success", "message": "All conversion files cleaned up"}
    return {"status": "info", "message": "No files to clean up"}

# Local entrypoint for testing
@app.local_entrypoint()
def main():
    """Example usage of the Docker to bootable .img converter"""
    
    # Convert an Alpine Linux container to bootable image
    result = convert_docker_to_bootable_img.remote(
        docker_image="alpine:latest",
        output_filename="alpine_bootable.img", 
        disk_size_mb=1024,
        filesystem_type="ext4"
    )
    
    print("Conversion result:", result)
    
    # List converted files
    files = list_conversion_files.remote()
    print("\nConverted files:", files)

if __name__ == "__main__":
    main()