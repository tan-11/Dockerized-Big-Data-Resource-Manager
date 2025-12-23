from flask import Flask, request, render_template, redirect, url_for, session, send_file
import subprocess
import re
import random
import time
import os
import json
import shutil
from werkzeug.security import generate_password_hash, check_password_hash
import fcntl


# Import our custom helper functions from utils.py
from utils import get_available_resources, parse_memory_to_mb, get_all_containers_details, extract_host_port, get_global_limits, generate_user_keys, provision_container, save_resource_request, get_all_requests

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SESSION_COOKIE_NAME'] = 'user_session'
USERS_FILE = "users.json"

# Function to help to find if user has a container
def get_user_container_details(username):
    # Get all containers from utils
    all_containers = get_all_containers_details()
    target_name = f"{username}_container"
    
    for container in all_containers:
        # We check exact name match
        if container['Names'] == target_name:
            return container
    return None
# ===========================register & login function===========================
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_new_user(username, password):
    users = load_users()
    if username in users:
        return False


    users[username] = generate_password_hash(password)

    with open(USERS_FILE, "w") as f:
        json.dump(users, f)
    return True

def verify_user(username, password):
    """Checks if username and password match."""
    users = load_users()
    if username not in users.keys():
        return False
    print("username yes")
    return check_password_hash(users[username], password)

# =============================================================

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username and not username.isalnum():
            error = "Username must be letters and numbers only."
        elif len(password) < 4:
            error = "Password is too short. At least 5 letters." 
        else:
            success = save_new_user(username, password)
            if success:
                return redirect(url_for('login'))
            else:
                error = "Username already taken."
    
    return render_template('user_register.html', error=error)

@app.route('/', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        is_match = verify_user(username, password)
        if is_match:
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            return render_template('user_login.html', error="Invalid username or password")
    
    return render_template('user_login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))      

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session['username']

    # Check if they already have a container
    existing_container = get_user_container_details(username)
    
    #get limits by admin
    limits = get_global_limits()
    max_cpu = limits['max_cpu']
    max_mem_gb = limits['max_memory_gb']
    max_ram_gb = limits['max_ram_gb']

    ssh_port = "N/A"
    if existing_container and 'Ports' in existing_container:
        # The string looks like "0.0.0.0:2501->22/tcp, ..."
        parts = existing_container['Ports'].split(',')
        for p in parts:
            # We look for the part mapping to port 22 inside the container
            if '->22' in p:
                try:
                    # Get the part before "->" (e.g., 0.0.0.0:2501)
                    host_side = p.split('->')[0]
                    # Get the part after the last colon (e.g., 2501)
                    ssh_port = host_side.split(':')[-1]
                except:
                    ssh_port = "Unknown"

    # Get server stats for the form (if they need to create one)
    resources = get_available_resources()

    requests = get_all_requests()
    if username in requests:
        user_request = requests[username] 
    else:
        user_request = ""

    # ---  Check for existing disk ---
    base_dir = os.path.dirname(os.path.abspath(__file__))
    disk_path = os.path.join(base_dir, 'user_data', f"{username}.img")
    
    has_existing_disk = False
    existing_disk_size = 0
    
    if os.path.exists(disk_path):
        has_existing_disk = True
        # Get size in GB
        existing_disk_size = os.path.getsize(disk_path) / (1024 * 1024 * 1024)

    return render_template(
        'dashboard.html',
        username=username,
        container=existing_container, # This determines what the HTML shows
        ssh_port=ssh_port,
        max_cpu=max_cpu,
        max_mem_gb=max_mem_gb,
        max_ram_gb=max_ram_gb,
        pending_request = user_request,
        has_existing_disk = has_existing_disk,
        existing_disk_size=existing_disk_size,
        **resources
    )

def setup_user_disk(username, size_gb=5):
    """Creates a fixed-size disk image for the user to limit storage."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    user_folder = os.path.join(base_dir, 'user_data', username)
    disk_image = os.path.join(base_dir, 'user_data', f"{username}.img")

    # 1. Create the folder where we will mount the disk
    print("create user file")
    os.makedirs(user_folder, exist_ok=True)

    print("user file ok")
    # 2. Check if the disk image already exists
    if not os.path.exists(disk_image):
        print(f"Creating {size_gb}GB disk for {username}...")
        
        # Create a blank file of specific size (e.g., 5GB)
        # command: dd if=/dev/zero of=username.img bs=1M count=5120
        size_mb = int(size_gb) * 1024
        subprocess.run(["dd", "if=/dev/zero", f"of={disk_image}", "bs=1M", f"count={size_mb}"], check=True)
        
        # Format the file as ext4 (like a USB drive)
        subprocess.run(["mkfs.ext4", disk_image], check=True)

    # 3. Mount the disk image to the folder
    # We check if it's already mounted to avoid errors
    is_mounted = subprocess.run(f"mount | grep {user_folder}", shell=True, stdout=subprocess.PIPE).stdout
    if not is_mounted:
        # Requires sudo usually, but if you run python as root it works.
        # If running as normal user, you might need to configure /etc/fstab or sudoers
        subprocess.run(["sudo", "mount", "-o", "loop", disk_image, user_folder], check=True)
        
        # Fix permissions so the user can write to it
        subprocess.run(["sudo", "chmod", "777", user_folder], check=True)
    
    return user_folder

@app.route('/delete_disk', methods=['POST'])
def delete_disk():
    if 'username' not in session: return redirect(url_for('login'))
    username = session['username']
    container_name = f"{username}_container"
    
    # 1. Force Stop & Remove Container 
    # (We MUST stop it, otherwise Linux won't let us delete the disk file)
    try:
        subprocess.run(["docker", "rm", "-f", container_name], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except:
        pass # It's okay if container didn't exist

    # 2. Define Paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    user_folder = os.path.join(base_dir, 'user_data', username)
    disk_image = os.path.join(base_dir, 'user_data', f"{username}.img")

    # 3. Unmount and Delete
    try:
        # A. Unmount the folder (Important! Linux locks mounted files)
        # We use lazy unmount (-l) just in case it's busy
        subprocess.run(["sudo", "umount", "-l", user_folder], check=False)
        
        # B. Delete the .img file (The Data)
        if os.path.exists(disk_image):
            os.remove(disk_image)
            print(f"Deleted disk image for {username}")
            
        # C. Delete the folder mount point (Cleanup)
        if os.path.exists(user_folder):
            # shutil.rmtree removes a folder and everything inside it
            shutil.rmtree(user_folder)
            
    except Exception as e:
        return f"Error deleting volume: {str(e)}"

    return redirect(url_for('dashboard'))

# --- ROUTE: Create Container (With Data Persistence) ---
@app.route('/request', methods=['POST'])
def create_container():
    if 'username' not in session: return redirect(url_for('login'))
    username = session['username']
    cpus_str = request.form['cpus']
    ram = request.form['Ram']
    try:
        memory = request.form['memory_old']
    except KeyError:
        memory = request.form['memory_new']
    print(memory)
    # --- ATOMIC RESOURCE VALIDATION ---
    lock_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'request.lock')
    with open(lock_path, 'w') as lockfile:
        fcntl.flock(lockfile, fcntl.LOCK_EX)
        available = get_available_resources()
        ram_str = f"{ram}g"
        if float(cpus_str) > available['cores_available'] or int(ram) > available['ram_available_gb'] or int(float(memory)) > available['host_free_disk_gb']:
            fcntl.flock(lockfile, fcntl.LOCK_UN)
            return "Insufficient Resources", 400
        success, msg = provision_container(username, cpus_str, memory, ram_str)
        fcntl.flock(lockfile, fcntl.LOCK_UN)
    if success:
        return redirect(url_for('dashboard'))
    else:
        return f"Error: {msg}"


@app.route('/request_special', methods=['POST'])
def request_special():
    if 'username' not in session: return redirect(url_for('login'))
    
    username = session['username']
    cpus = request.form.get('cpus')
    ram = request.form.get('ram')
    memory_gb = request.form.get('memory')
    reason = request.form.get('reason')
    
    # Validate that all required fields are present
    if not cpus or not ram or not memory_gb or not reason:
        return "Missing required fields", 400
    
    # For special requests, we allow submission even if resources are insufficient
    # The admin will validate and approve when resources become available
    ram_str = f"{ram}g"
    
    # Save to JSON
    save_resource_request(username, cpus, memory_gb, ram_str, reason)
    
    # Redirect back to dashboard
    return redirect(url_for('dashboard'))

@app.route('/control/<action>', methods=['POST'])
def control_container(action):
    if 'username' not in session: return redirect(url_for('login'))
    username = session['username']
    container_name = f"{username}_container"

    if action == "stop":
        subprocess.run(["docker", "stop", container_name])
    elif action == "start":
        setup_user_disk(username)
        subprocess.run(["docker", "start", container_name])
    elif action == "delete":
        # Force remove the container. 
        # Because we used -v (Volume), the data in 'user_data' folder remains safe!
        subprocess.run(["docker", "rm", "-f", container_name])
    
    return redirect(url_for('dashboard'))

@app.route('/download_key')
def download_key():
    if 'username' not in session: return redirect(url_for('login'))
    username = session['username']
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    key_path = os.path.join(base_dir, 'user_data', username, f"{username}_key.pem")
    
    if os.path.exists(key_path):
        return send_file(key_path, as_attachment=True)
    else:
        return "Key file not found. Please create a container first.", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)