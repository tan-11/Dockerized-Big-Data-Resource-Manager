# To check Server Resources and Availability

import os
import subprocess
import json
import psutil
import time
import random
import shutil

REQUESTS_FILE = 'requests.json'
SETTINGS_FILE = 'settings.json'

# For server status and resource display
def parse_memory_to_mb(mem):
    return f"{mem}g", (int(mem) * 1024)



def get_available_resources():
    """Checks Docker for allocated resources and returns what's available."""
    # 1. CPU & RAM
    host_total_cores = os.cpu_count() - 2
    host_total_ram_gb = (psutil.virtual_memory().total / (1024 * 1024 * 1024)) - 10
    allocated_cpus = 0
    allocated_ram_gb = 0
    try:
        container_ids = subprocess.check_output(
            ["docker", "ps", "-q"]
        ).decode('utf-8').splitlines()
        if container_ids:
            inspect_output = subprocess.check_output(
                ["docker", "inspect"] + container_ids
            ).decode('utf-8')
            container_details = json.loads(inspect_output)
            for details in container_details:
                nano_cpus = details['HostConfig']['NanoCpus']
                if nano_cpus > 0:
                    allocated_cpus += nano_cpus / 1_000_000_000
                memory_bytes = details['HostConfig']['Memory']
                if memory_bytes > 0:
                    allocated_ram_gb += memory_bytes / (1024 * 1024 * 1024)
    except Exception:
        pass
    
    # 2. Disk usage
    base_dir = os.path.dirname(os.path.abspath(__file__))
    user_data_dir = os.path.join(base_dir, 'user_data')

    total, used, free = shutil.disk_usage(".")
    host_total_disk_gb = total / (1024**3)
    total_allocated_gb = 0
    print(f"used disk storage: {used}")
    if os.path.exists(user_data_dir):
        for f in os.listdir(user_data_dir):
            if f.endswith('.img'):
                path = os.path.join(user_data_dir, f)
                # os.path.getsize returns the logical max size (e.g., 5GB)
                # not the physical usage on disk.
                total_allocated_gb += os.path.getsize(path)
    
    total_allocated_gb /= (1024**3)
    host_free_disk_gb = (host_total_disk_gb - total_allocated_gb) - 50
    
    return {
        "cores_available": host_total_cores - allocated_cpus,
        "ram_available_gb": host_total_ram_gb - allocated_ram_gb,
        "host_total_cores": host_total_cores,
        "host_total_ram_gb": host_total_ram_gb,
        "host_total_disk_gb": host_total_disk_gb,
        "host_free_disk_gb": host_free_disk_gb
    }

# For Admin Monitoring - Get all containers details
def get_all_containers_details():
    """Gets rich details for all containers, including allocated resources."""
    containers = []
    try:
        # Get the list of all container IDs first
        container_ids = subprocess.check_output(
            ["docker", "ps", "-a", "-q"]
        ).decode('utf-8').splitlines()

        if not container_ids:
            return []

        # Use 'docker inspect' to get the full JSON details for all containers at once
        inspect_output = subprocess.check_output(
            ["docker", "inspect"] + container_ids
        ).decode('utf-8')
        
        all_details = json.loads(inspect_output)

        # Process each container's details into a clean format
        for details in all_details:
            # Helper to format port bindings cleanly
            ports = details.get('NetworkSettings', {}).get('Ports', {})
            port_mappings = []
            for internal, external_list in ports.items():
                if external_list:
                    for external in external_list:
                        port_mappings.append(f"{external['HostIp']}:{external['HostPort']}->{internal}")
            
            containers.append({
                'ID': details['Id'],
                'Names': details['Name'].lstrip('/'),
                'Image': details['Config']['Image'],
                'Status': details['State']['Status'].capitalize(),
                'FullStatus': f"{details['State']['Status'].capitalize()} ({details['State']['ExitCode']})" if details['State']['Status'] != 'running' else 'Running',
                'Ports': ', '.join(port_mappings) or 'N/A',
                'CPUs': details['HostConfig'].get('NanoCpus', 0) / 1_000_000_000,
                'MemoryMB': details['HostConfig'].get('Memory', 0) / (1024 * 1024)
            })

    except Exception as e:
        print(f"Error getting container details: {e}")
        return []

    return containers
    
def extract_host_port(port_str):
    if '->' not in port_str:
        return None
    
    left = port_str.split('->')[0]   # before "->"
    parts = left.split(':')
    
    # host port is always the last part
    host_part = parts[-1].strip()

    return int(host_part)


def get_global_limits():
    """Reads the global resource limits set by the admin."""
    defaults = {
        'max_cpu': 2.0,       # Default limit if file missing
        'max_memory_gb': 8, # Default 4GB
        'max_ram_gb': 4 
    }
    
    if not os.path.exists(SETTINGS_FILE):
        return defaults
        
    try:
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    except:
        return defaults

def save_global_limits(cpu, mem_gb, ram_gb):
    """Saves the limits to the JSON file."""
    data = {
        'max_cpu': float(cpu),
        'max_memory_gb': int(mem_gb),
        'max_ram_gb' : int(ram_gb)
    }
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(data, f)


def generate_user_keys(username):
    """Generates an SSH key pair for the user."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # Save keys inside the user's persistent data folder
    key_dir = os.path.join(base_dir, 'user_data', username)
    os.makedirs(key_dir, exist_ok=True)

    private_key_path = os.path.join(key_dir, f"{username}_key.pem")
    public_key_path = os.path.join(key_dir, f"{username}_key.pem.pub")

    # If key already exists, delete it to ensure a fresh key for the new container
    if os.path.exists(private_key_path):
        os.remove(private_key_path)
    if os.path.exists(public_key_path):
        os.remove(public_key_path)

    # Generate Key Pair (RSA 2048 bit, no passphrase)
    cmd = [
        "ssh-keygen", 
        "-t", "rsa", 
        "-b", "2048", 
        "-f", private_key_path, 
        "-q",       # Quiet mode
        "-N", ""    # Empty passphrase
    ]
    subprocess.run(cmd, check=True)
    
    # Read the Public Key so we can inject it into the container
    with open(public_key_path, 'r') as f:
        public_key_str = f.read().strip()
        
    return private_key_path, public_key_str

def save_resource_request(username, cpus, mem_gb, ram_gb, reason):
    """Saves a pending request to JSON."""
    if os.path.exists(REQUESTS_FILE):
        with open(REQUESTS_FILE, 'r') as f:
            requests = json.load(f)
    else:
        requests = {}

    requests[username] = {
        'cpu': cpus,
        'memory_gb': int(mem_gb),
        'ram_gb': ram_gb,
        'reason': reason,
        'timestamp': time.time()
    }
    
    with open(REQUESTS_FILE, 'w') as f:
        json.dump(requests, f)

def get_all_requests():
    if not os.path.exists(REQUESTS_FILE): return {}
    with open(REQUESTS_FILE, 'r') as f:
        return json.load(f)

def delete_request(username):
    requests = get_all_requests()
    if username in requests:
        del requests[username]
        with open(REQUESTS_FILE, 'w') as f:
            json.dump(requests, f)

def provision_container(username, cpus, mem_gb, ram_gb):
    # --- 2. Data Persistence Setup ---
    # We create a folder on the HOST machine for this user
    try:
        from app import setup_user_disk
        # This creates a 5GB limit for this user
        user_data_path = setup_user_disk(username, size_gb=mem_gb) 

        private_key_path, pubkey_str = generate_user_keys(username)

        ssh_port = random.randint(2000, 3000)
        containers = get_all_containers_details()
        used_ports = {
            extract_host_port(p)
            for c in containers 
            for p in c['Ports'].split(',') 
            if p != 'N/A'}
            
        attempts = 0
        while ssh_port in used_ports:
            ssh_port += 1
            if ssh_port > 3000: # Wrap around
                ssh_port = 2000
            attempts += 1
            if attempts > 1000: # We checked every port from 2000-3000
                return "Error: No SSH ports available on server!", 500


        container_name = f"{username}_container"
        mem_str = f"{mem_gb}m"

        cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "--cpus", cpus,
            "--memory", ram_gb,         #ram
            "-p", f"{ssh_port}:22",
           
            "-v", f"{user_data_path}:/home/{username}", 
            "hadoop_container" 
        ]
        subprocess.run(cmd, check=True)

        print("Waiting for HDFS to be ready...")
        hdfs_ready = False
        for i in range(10):  # Try 10 times (approx 50 seconds)
            try:
                # We try to list the root directory. If this succeeds, HDFS is up.
                subprocess.run(
                    ["docker", "exec", container_name, "hdfs", "dfs", "-ls", "/"], 
                    check=True, 
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL
                )
                hdfs_ready = True
                print("HDFS is ready!")
                break
            except subprocess.CalledProcessError:
                print(f"HDFS not ready yet (Attempt {i+1}/10)...")
                time.sleep(5)

        if not hdfs_ready:
            # Depending on your preference, you might want to cleanup and fail here
            print("WARNING: HDFS setup timed out. User may need to start it manually.")
        
        # 1. create the user
        subprocess.run(["docker", "exec", container_name, "bash", "-c", f"id -u {username} || useradd -m -s /bin/bash {username}"], check=True)
        subprocess.run(["docker", "exec", container_name, "chown", "-R", f"{username}:{username}", f"/home/{username}"], check=True)
        subprocess.run(["docker", "exec", container_name, "chmod", "755", f"/home/{username}"], check=True)

        # 2. Setup SSH
        subprocess.run(["docker", "exec", "-u", username, container_name, "mkdir", "-p", f"/home/{username}/.ssh"], check=True)
        subprocess.run(["docker", "exec", "-u", username, container_name, "chmod", "700", f"/home/{username}/.ssh"], check=True)
        subprocess.run(["docker", "exec", "-u", username, container_name, "bash", "-c", f"echo '{pubkey_str}' >> /home/{username}/.ssh/authorized_keys"], check=True)
        subprocess.run(["docker", "exec", "-u", username, container_name, "chmod", "600", f"/home/{username}/.ssh/authorized_keys"], check=True)

        #3. Grant Sudo 
        subprocess.run(["docker", "exec", container_name, "usermod", "-aG", "sudo", username], check=True)

        #4. Create and set ownership for the user's HDFS home directory
        subprocess.run(["docker", "exec", container_name, "hdfs", "dfs", "-mkdir", "-p", f"/user/{username}"], check=True)
        subprocess.run(["docker", "exec", container_name, "hdfs", "dfs", "-chown", f"{username}:{username}", f"/user/{username}"], check=True)

        return True, "Container Created Successfully"

    except Exception as e:
        return False, str(e)