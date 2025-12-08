from flask import Flask, render_template, redirect, url_for, request, session
import subprocess
from utils import get_all_containers_details
import os
from utils import get_global_limits, save_global_limits, get_all_requests, delete_request, provision_container
from app import create_container

app = Flask(__name__)

app.secret_key = os.urandom(24)

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
    return render_template('monitoring.html', containers=all_containers)

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
        
        # CALL THE SHARED CREATION FUNCTION
        # This bypasses the global limits because we are calling it directly!
        success, msg = provision_container(username, req['cpu'], req['memory_gb'], req['ram_gb'])
        
        if success:
            delete_request(username) # Remove from pending list
            print(f"Approved and created container for {username}")
        else:
            return f"Error creating container: {msg}"
            
    return redirect(url_for('admin_requests'))

@app.route('/reject/<username>', methods=['POST'])
@login_required
def reject_request(username):
    delete_request(username)
    return redirect(url_for('admin_requests'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7000)