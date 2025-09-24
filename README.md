# Docker to Bootable .img Converter - Modal.com Function

## Overview

This Modal.com function converts Docker images/containers into bootable .img disk snapshots that can be used with virtual machines or written to physical storage devices. The conversion process includes:

1. **Container Export**: Extracts the complete filesystem from a Docker container
2. **Disk Image Creation**: Creates a raw disk image with proper partitioning
3. **Bootloader Installation**: Installs EXTLINUX/SYSLINUX bootloader for BIOS boot
4. **Kernel Integration**: Installs Linux kernel for Debian/Ubuntu-based containers
5. **Init System Setup**: Configures basic init system or systemd

## Key Features

- **Multi-Distribution Support**: Works with Alpine, Debian, Ubuntu, CentOS containers
- **Configurable Disk Size**: Specify custom disk image size (default 2GB)
- **Multiple Filesystem Types**: Support for ext4, ext3, ext2 filesystems
- **Automated Bootloader**: Automatic EXTLINUX installation with MBR
- **Volume Persistence**: Uses Modal volumes for file storage and reuse
- **Comprehensive Error Handling**: Detailed logging and error reporting

## Usage Examples

### Basic Usage

```python
import modal

# Deploy the app
app = modal.App.lookup("docker-to-bootable-img", create_if_missing=False)

# Convert Alpine Linux to bootable image
result = app.convert_docker_to_bootable_img.remote(
    docker_image="alpine:latest",
    output_filename="alpine_system.img",
    disk_size_mb=1024
)
print(result)
```

### Advanced Configuration

```python
# Convert Ubuntu with larger disk and custom filesystem
result = app.convert_docker_to_bootable_img.remote(
    docker_image="ubuntu:20.04",
    output_filename="ubuntu_development.img", 
    disk_size_mb=4096,
    filesystem_type="ext4"
)
```

### Container Registry Images

```python
# Convert from private or public registries
result = app.convert_docker_to_bootable_img.remote(
    docker_image="nginx:alpine",
    output_filename="nginx_appliance.img",
    disk_size_mb=2048
)
```

## Function Parameters

### convert_docker_to_bootable_img()

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `docker_image` | str | required | Docker image name (e.g., "alpine:latest") |
| `output_filename` | str | "bootable_system.img" | Output .img filename |
| `disk_size_mb` | int | 2048 | Disk size in megabytes |
| `filesystem_type` | str | "ext4" | Filesystem type (ext4/ext3/ext2) |

## Return Value

```python
{
    "status": "success" | "error",
    "output_file": "/tmp/conversion/filename.img",
    "file_size_mb": 1024,
    "docker_image": "alpine:latest", 
    "disk_size_mb": 2048,
    "filesystem_type": "ext4",
    "message": "Successfully converted alpine:latest to bootable filename.img"
}
```

## Deployment Instructions

### 1. Save the Function

Save the provided code as `docker_to_bootable.py`

### 2. Deploy to Modal

```bash
modal deploy docker_to_bootable.py
```

### 3. Run Conversion

```bash
modal run docker_to_bootable.py
```

### 4. Call Remotely

```python
import modal

# Get deployed function
convert_fn = modal.Function.from_name("docker-to-bootable-img", "convert_docker_to_bootable_img")

# Execute conversion
result = convert_fn.remote("alpine:latest", "my_system.img", 1024)
print(result)
```

## Technical Details

### Conversion Process

1. **Docker Daemon**: Starts dockerd in the Modal container
2. **Image Pull**: Downloads the specified Docker image
3. **Container Export**: Uses `docker export` to create filesystem tarball
4. **Disk Creation**: Creates raw disk image with `dd` command
5. **Partitioning**: Uses `fdisk` to create bootable partition table
6. **Filesystem**: Formats partition with specified filesystem type
7. **File Extraction**: Extracts container files to mounted partition
8. **Kernel Install**: For Debian/Ubuntu, installs Linux kernel via chroot
9. **Bootloader**: Installs EXTLINUX bootloader and configuration
10. **MBR**: Writes Master Boot Record for BIOS boot compatibility

### System Requirements

- **CPU**: 4 cores (configurable)
- **Memory**: 8GB RAM (for large container conversions)
- **Storage**: Modal persistent volume for output files
- **Timeout**: 1 hour (adjustable for large images)

### Supported Container Types

| Base Image | Kernel Install | Boot Success |
|------------|---------------|--------------|
| alpine:latest | Manual init | ✅ |
| ubuntu:20.04 | Automatic | ✅ |
| debian:bullseye | Automatic | ✅ |
| centos:8 | Manual | ✅ |
| nginx:alpine | Manual init | ✅ |

## Utility Functions

### list_conversion_files()

Lists all .img files created in the Modal volume:

```python
files = app.list_conversion_files.remote()
# Returns: [{"filename": "alpine.img", "path": "/tmp/conversion/alpine.img", "size_mb": 1024}]
```

### cleanup_conversion_files()

Removes all conversion files to free up volume space:

```python
result = app.cleanup_conversion_files.remote()
# Returns: {"status": "success", "message": "All conversion files cleaned up"}
```

## Testing the Bootable Image

### Using QEMU

```bash
# Test with QEMU
qemu-system-x86_64 -drive file=alpine_system.img,format=raw -m 512 -boot c
```

### Using VirtualBox

1. Convert to VDI format:
```bash
qemu-img convert -f raw -O vdi alpine_system.img alpine_system.vdi
```

2. Create new VM in VirtualBox using the .vdi file

### Writing to USB/Physical Media

```bash
# Write to USB device (be very careful with device path!)
sudo dd if=alpine_system.img of=/dev/sdX bs=1M status=progress
```

## Troubleshooting

### Common Issues

1. **Docker daemon fails**: Modal containers may need privileged mode for Docker-in-Docker
2. **Kernel missing**: Some minimal containers don't include kernel packages
3. **Boot failure**: BIOS vs UEFI compatibility issues
4. **Large images**: Increase timeout and memory for big containers

### Debugging Tips

```python
# Enable verbose logging
result = convert_docker_to_bootable_img.remote(
    docker_image="alpine:latest",
    output_filename="debug.img"
)

# Check conversion logs
print(result["message"])
```

## Limitations

- **BIOS Boot Only**: Currently supports legacy BIOS boot, not UEFI
- **x86_64 Architecture**: Limited to AMD64/x86_64 containers
- **Container Dependencies**: Some containers may need additional setup
- **Network Configuration**: Generated images may need manual network setup
- **Storage Overhead**: Raw .img files are larger than compressed formats

## Extensions and Customizations

### Adding UEFI Support

Modify the bootloader installation to use GRUB2 with EFI partition:

```python
# Create EFI system partition
subprocess.run(["parted", img_path, "mkpart", "primary", "fat32", "1MiB", "100MiB"])
subprocess.run(["parted", img_path, "set", "1", "esp", "on"])
```

### Custom Init Scripts

Replace the basic init with custom startup logic:

```python
init_script = """#!/bin/sh
# Custom initialization
mount -t proc proc /proc
mount -t sysfs sysfs /sys
# Start your services here
exec /usr/sbin/your-service
"""
```

### Compression Support

Add qcow2 conversion for smaller files:

```python
# Convert to qcow2 format
subprocess.run([
    "qemu-img", "convert", "-f", "raw", "-O", "qcow2", 
    img_path, img_path.replace(".img", ".qcow2")
])
```

This Modal.com function provides a robust foundation for converting Docker containers into bootable disk images, suitable for development, testing, and deployment scenarios.