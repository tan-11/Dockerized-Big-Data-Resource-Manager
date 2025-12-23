from flask import Flask, render_template, redirect, url_for, request, session
import subprocess
from utils import get_all_containers_details
import os
from utils import get_global_limits, save_global_limits, get_all_requests, delete_request, provision_container, get_available_resources
from app import create_container, get_user_container_details
import fcntl

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SESSION_COOKIE_NAME'] = 'admin_session'

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "123456" 

def login_required(func):
    def wrapper(*args, **kwargs):
        if "logged_in" not in session:
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("admin"))
        else:
            error = "Invalid username or password"

    return render_template("admin_login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# Admin Monitoring
@app.route('/')
@login_required
def admin():
    """Displays the admin monitoring page."""
    all_containers = get_all_containers_details()
    resources = get_available_resources()
    return render_template('monitoring.html', containers=all_containers, **resources)

@app.route('/stop/<container_id>', methods=['POST'])
@login_required
def stop_container(container_id):
    """Stops a specific container."""
    if container_id:
        subprocess.run(["docker", "stop", container_id], check=True)
    return redirect(url_for('admin')) # Redirect back to the monitoring page

@app.route('/start/<container_id>', methods=['POST'])
@login_required
def start_container(container_id):
    """Starts a specific container."""
    if container_id:
        subprocess.run(["docker", "start", container_id], check=True)
    return redirect(url_for('admin')) # Redirect back to the monitoring page

@app.route('/delete/<container_id>', methods=['POST'])
@login_required
def delete_container(container_id):
    """Starts a specific container."""
    if container_id:
        subprocess.run(["docker", "rm", container_id], check=True)
    return redirect(url_for('admin')) # Redirect back to the monitoring page

# In admin.py

@app.route('/delete_all_containers', methods=['POST'])
@login_required
def delete_all_containers():
    """Forces stop and removal of ALL user containers."""
    
    # 1. Get list of all containers
    containers = get_all_containers_details()
    
    count = 0
    for c in containers:
        # Safety Check: Only delete containers created by our app
        # (We assume they all end in "_container" based on your provision logic)
        name = c.get('Names', '')
        
        if name.endswith('_container'):
            try:
                # Docker remove with -f (Force) kills it even if running
                subprocess.run(["docker", "rm", "-f", c['ID']], check=False)
                count += 1
            except Exception as e:
                print(f"Failed to delete {name}: {e}")

    print(f"Admin deleted {count} containers.")
    return redirect(url_for('admin'))
    
@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        cpu = request.form.get('max_cpu')
        mem = request.form.get('max_memory_gb')
        ram = request.form.get('max_ram_gb')
        save_global_limits(cpu, mem, ram)
        return redirect(url_for('admin'))
    # Load current settings to fill the form
    current_limits = get_global_limits()
    return render_template('admin_setting.html', limits=current_limits)

@app.route('/requests')
@login_required
def admin_requests():
    requests = get_all_requests()
    return render_template('admin_request.html', requests=requests)

@app.route('/approve/<username>', methods=['POST'])
@login_required
def approve_request(username):
    requests = get_all_requests()
    if username in requests:
        req = requests[username]
        lock_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'request.lock')
        with open(lock_path, 'w') as lockfile:
            fcntl.flock(lockfile, fcntl.LOCK_EX)
            # Check if user already has a container (atomic)
            existing_container = get_user_container_details(username)
            if existing_container:
                fcntl.flock(lockfile, fcntl.LOCK_UN)
                return f"User '{username}' already has an active container. A user can only have one container at a time.", 400
            available = get_available_resources()
            ram_str = req['ram_gb']  # Already in format like "4g"
            cpus_requested = float(req['cpu'])
            ram_requested = int(ram_str.lower().replace("g", ""))
            memory_requested = req['memory_gb']
            if cpus_requested > available['cores_available']:
                fcntl.flock(lockfile, fcntl.LOCK_UN)
                return f"Insufficient CPU resources. Requested: {cpus_requested}, Available: {available['cores_available']}", 400
            if ram_requested > available['ram_available_gb']:
                fcntl.flock(lockfile, fcntl.LOCK_UN)
                return f"Insufficient RAM. Requested: {ram_requested}GB, Available: {available['ram_available_gb']}GB", 400
            if memory_requested > available['host_free_disk_gb']:
                fcntl.flock(lockfile, fcntl.LOCK_UN)
                return f"Insufficient disk space. Requested: {memory_requested}GB, Available: {available['host_free_disk_gb']}GB", 400
            # Resources are available, proceed with provisioning
            success, msg = provision_container(username, req['cpu'], req['memory_gb'], req['ram_gb'])
            fcntl.flock(lockfile, fcntl.LOCK_UN)
        if success:
            delete_request(username) # Remove from pending list
            print(f"Approved and created container for {username}")
        else:
            return f"Error creating container: {msg}", 500
    return redirect(url_for('admin_requests'))

@app.route('/reject/<username>', methods=['POST'])
@login_required
def reject_request(username):
    delete_request(username)
    return redirect(url_for('admin_requests'))

@app.route('/delete_user_data/<username>', methods=['POST'])
@login_required
def delete_user_data(username):
    """Deletes all persistent data for a user: .img file and user_data folder."""
    import shutil
    import os
    base_dir = os.path.dirname(os.path.abspath(__file__))
    user_data_dir = os.path.join(base_dir, 'user_data')
    user_folder = os.path.join(user_data_dir, username)
    user_img = os.path.join(user_data_dir, f"{username}.img")

    # Remove user folder (with SSH keys, hdfs, etc)
    if os.path.exists(user_folder) and os.path.isdir(user_folder):
        shutil.rmtree(user_folder)
    # Remove user .img file
    if os.path.exists(user_img):
        os.remove(user_img)
    return redirect(url_for('admin'))

@app.route('/storage')
@login_required
def storage():
    import os
    from utils import get_all_containers_details
    user_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'user_data')
    containers = get_all_containers_details()
    users_with_container = set()
    for c in containers:
        if c['Names'].endswith('_container'):
            users_with_container.add(c['Names'][:-10])
    users = []
    for fname in os.listdir(user_data_dir):
        if fname.endswith('.img'):
            username = fname[:-4]
            img_path = os.path.join(user_data_dir, fname)
            size_gb = os.path.getsize(img_path) / (1024**3)
            is_mounted = username in users_with_container
            users.append({
                'username': username,
                'img': fname,
                'size_gb': f"{size_gb:.2f}",
                'mounted': is_mounted
            })
    return render_template('storage.html', users=users)

@app.route('/delete_user_data', methods=['POST'])
@login_required
def delete_user_data_form():
    username = request.form.get('username')
    if username:
        import shutil, os
        base_dir = os.path.dirname(os.path.abspath(__file__))
        user_data_dir = os.path.join(base_dir, 'user_data')
        user_folder = os.path.join(user_data_dir, username)
        user_img = os.path.join(user_data_dir, f"{username}.img")
        # Try to unmount before deleting (ignore errors)
        if os.path.exists(user_folder) and os.path.isdir(user_folder):
            try:
                subprocess.run(["sudo", "umount", "-l", user_folder], check=False)
            except Exception:
                pass
            shutil.rmtree(user_folder)
        if os.path.exists(user_img):
            os.remove(user_img)
    return redirect(url_for('storage'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7000)
