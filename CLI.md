# Docker to Bootable .img Converter - CLI Interface

## Overview

The enhanced Modal.com function now includes a comprehensive CLI interface built with Click, allowing you to control the Docker-to-bootable conversion process directly from the command line. This provides both interactive and scripted automation capabilities.

## Installation and Setup

### 1. Deploy the Modal Function

```bash
# Deploy the app to Modal
modal deploy docker-bootable-cli.py

# Verify deployment
modal app list
```

### 2. Install Local Dependencies

```bash
pip install click modal
```

## CLI Commands Reference

### Basic Command Structure

```bash
python docker-bootable-cli.py [GLOBAL_OPTIONS] COMMAND [COMMAND_OPTIONS]
```

### Global Options

- `--verbose, -v`: Enable verbose output for debugging
- `--help`: Show help message

## Core Commands

### 1. Convert Command

Convert a Docker image to a bootable .img file:

```bash
python docker-bootable-cli.py convert [OPTIONS] DOCKER_IMAGE
```

**Options:**
- `--output, -o`: Output filename (default: bootable_system.img)
- `--size, -s`: Disk size in MB (default: 2048)
- `--filesystem, -f`: Filesystem type [ext4|ext3|ext2] (default: ext4)
- `--wait/--no-wait`: Wait for completion vs. async mode (default: wait)

**Examples:**

```bash
# Basic conversion
python docker-bootable-cli.py convert alpine:latest

# Custom output and size
python docker-bootable-cli.py convert ubuntu:20.04 --output ubuntu-dev.img --size 4096

# Different filesystem type
python docker-bootable-cli.py convert nginx:alpine --filesystem ext3 --size 1024

# Asynchronous conversion (returns immediately)
python docker-bootable-cli.py convert large-image:latest --no-wait

# Verbose mode
python docker-bootable-cli.py --verbose convert debian:bullseye
```

### 2. List Command

List all converted .img files stored in the Modal volume:

```bash
python docker-bootable-cli.py list
```

**Output:**
```
Found 3 .img file(s):

Filename                       Size (MB)    Path
----------------------------------------------------------------------
alpine_system.img              1024         /tmp/conversion/alpine_system.img
ubuntu-dev.img                 4096         /tmp/conversion/ubuntu-dev.img
nginx_appliance.img            2048         /tmp/conversion/nginx_appliance.img
```

### 3. Cleanup Command

Remove all conversion files from the Modal volume:

```bash
python docker-bootable-cli.py cleanup
```

**Features:**
- Interactive confirmation prompt
- Clears all .img files and temporary data
- Frees up Modal volume space

### 4. Status Command

Check the status of asynchronous conversions:

```bash
python docker-bootable-cli.py status FUNCTION_CALL_ID
```

**Example:**
```bash
# Start async conversion
python docker-bootable-cli.py convert large-image:latest --no-wait
# Output: Function call ID: fc-abc123

# Check status later
python docker-bootable-cli.py status fc-abc123
```

**Status Responses:**
- `✓ Conversion completed successfully!` - Process finished
- `⏳ Conversion still in progress...` - Still running
- `✗ Conversion failed!` - Error occurred

### 5. Examples Command

Display comprehensive usage examples:

```bash
python docker-bootable-cli.py examples
```

## Modal Integration Modes

### 1. Using Modal Run (Recommended)

Run the CLI through Modal's command system:

```bash
# Deploy and run in one command
modal run docker-bootable-cli.py convert alpine:latest

# Run with specific entrypoint
modal run docker-bootable-cli.py::main convert ubuntu:20.04 --size 4096

# Test mode
modal run docker-bootable-cli.py::test
```

### 2. Direct Python Execution

Run the CLI locally (requires Modal authentication):

```bash
# Set up Modal credentials
modal token new

# Run CLI commands
python docker-bootable-cli.py convert alpine:latest
python docker-bootable-cli.py list
python docker-bootable-cli.py cleanup
```

### 3. Programmatic Access

Use the CLI functions in Python scripts:

```python
import modal

# Get the deployed app
app = modal.App.lookup("docker-to-bootable-img")

# Call functions directly
result = app.convert_docker_to_bootable_img.remote(
    docker_image="alpine:latest",
    output_filename="custom.img",
    disk_size_mb=1024
)

# List files
files = app.list_conversion_files.remote()
print(files)
```

## Asynchronous Operations

### Starting Async Conversions

Large Docker images benefit from asynchronous processing:

```bash
# Start conversion without waiting
python docker-bootable-cli.py convert large-enterprise-app:latest --no-wait

# Output provides function call ID for tracking
# Function call ID: fc-a1b2c3d4
```

### Monitoring Progress

```bash
# Check status
python docker-bootable-cli.py status fc-a1b2c3d4

# Possible outputs:
# ⏳ Conversion still in progress...
# ✓ Conversion completed successfully!
# ✗ Conversion failed!
```

### Batch Processing

Process multiple images asynchronously:

```bash
#!/bin/bash
# batch-convert.sh

images=("alpine:latest" "ubuntu:20.04" "nginx:alpine" "python:3.11")

for image in "${images[@]}"; do
    output="${image//[:\/]/_}.img"
    echo "Starting conversion of $image..."
    python docker-bootable-cli.py convert "$image" --output "$output" --no-wait
done

echo "All conversions started. Check status with 'list' command."
```

## Error Handling and Debugging

### Verbose Mode

Enable detailed logging for troubleshooting:

```bash
python docker-bootable-cli.py --verbose convert problematic-image:latest
```

### Common Error Scenarios

1. **Docker Image Not Found**
```bash
✗ Error: docker pull failed
# Solution: Verify image name and registry access
```

2. **Insufficient Disk Space**
```bash
✗ Error: No space left on device
# Solution: Reduce --size parameter or cleanup old files
```

3. **Network Issues**
```bash
✗ Error: Unable to pull Docker image
# Solution: Check network connectivity and registry access
```

4. **Modal Authentication**
```bash
✗ Error: Authentication failed
# Solution: Run `modal token new` to set up credentials
```

## Configuration and Customization

### Default Settings

Modify default values in the CLI code:

```python
@cli.command()
@click.option('--size', '-s', default=2048, type=int)  # Default disk size
@click.option('--filesystem', '-f', default='ext4')    # Default filesystem
```

### Environment Variables

Set Modal environment variables:

```bash
export MODAL_TOKEN_ID="your_token_id"
export MODAL_TOKEN_SECRET="your_token_secret"
export MODAL_ENVIRONMENT="your_environment"
```

### Custom Entrypoints

Create specialized entry points for different use cases:

```python
@app.local_entrypoint()
def batch_convert():
    """Convert multiple predefined images"""
    images = ["alpine:latest", "ubuntu:20.04", "nginx:alpine"]
    
    for image in images:
        result = convert_docker_to_bootable_img.remote(
            docker_image=image,
            output_filename=f"{image.replace(':', '_')}.img"
        )
        print(f"Converted {image}: {result['status']}")
```

## Integration Examples

### CI/CD Pipeline

```yaml
# .github/workflows/build-appliances.yml
name: Build Bootable Appliances

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
          
      - name: Install dependencies
        run: |
          pip install modal click
          
      - name: Setup Modal credentials
        env:
          MODAL_TOKEN_ID: ${{ secrets.MODAL_TOKEN_ID }}
          MODAL_TOKEN_SECRET: ${{ secrets.MODAL_TOKEN_SECRET }}
        run: |
          modal token set
          
      - name: Build bootable images
        run: |
          modal run docker-bootable-cli.py convert myapp:latest --output myapp-v${{ github.sha }}.img
```

### Dockerfile Integration

```dockerfile
# Build stage
FROM python:3.11 AS builder
COPY requirements.txt .
RUN pip install -r requirements.txt

# Deploy and convert stage  
FROM modal/base:latest
COPY --from=builder /app .
COPY docker-bootable-cli.py .

# Convert current image to bootable
RUN python docker-bootable-cli.py convert $(hostname):latest --output $(hostname)-bootable.img
```

### Monitoring Script

```bash
#!/bin/bash
# monitor-conversions.sh

echo "Docker to Bootable .img Converter - Status Monitor"
echo "================================================"

while true; do
    echo "$(date): Checking conversion status..."
    
    files=$(python docker-bootable-cli.py list 2>/dev/null)
    if [ $? -eq 0 ]; then
        echo "$files"
    else
        echo "Error checking status"
    fi
    
    echo "---"
    sleep 30
done
```

This CLI interface transforms the Modal function into a powerful, user-friendly tool for automated Docker-to-bootable conversion workflows, supporting both interactive use and programmatic automation.