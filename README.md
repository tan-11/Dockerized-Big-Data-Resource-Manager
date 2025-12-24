# PowerDockerLab
### Containerized Big Data Learning Environment (PaaS)

## 1. PROJECT OVERVIEW
**PowerDockerLab** is a lightweight Platform-as-a-Service (PaaS) designed to automate the deployment of Big Data learning environments. Unlike traditional Virtual Machines (VMs) which are resource-heavy, this platform utilizes Docker containers to provide students with instant, isolated access to Hadoop, Kafka, and Spark clusters.

The system features a "Self-Service" web portal that allows users to provision environments, manages persistent storage so data survives restarts, and enforces strict resource governance (CPU, RAM, & Storage quotas) to ensure fair multi-tenant usage.

---

## 2. KEY FEATURES
* **Self-Service Web Portal:** Minimalist Flask-based UI for one-click container provisioning.
* **Automated Big Data Stack:** Instantly deploys pre-configured Hadoop (HDFS), Spark, and Kafka containers.
* **Resource Governance:**
    * Enforces global CPU and RAM limits per user to prevent host exhaustion.
    * Locking mechanism to handle concurrent user requests safely.
* **Data Persistence:** "Host-Path" volume binding ensures student data is saved to the host disk (`/user_data`) and persists across sessions.
* **Admin Dashboard:**
    * Real-time monitoring of host resources (CPU/RAM/Disk).
    * Ability to terminate non-compliant containers.
    * Approval workflow for "Super User" high-resource requests.
* **Security:** SSH Key-based authentication for container access.

---

## 3. SYSTEM REQUIREMENTS
* **Operating System:** Linux
* **Container Engine:** Docker Engine (v20.10+)
* **Language Runtime:** Python 3.8+
* **Dependencies:** See `requirements.txt`

---

## 4. INSTALLATION & SETUP

### Step 1: Install System Dependencies
Review & follow the steps in `docker_install.txt`.

### Step 2: Clone the Repository
```bash
git clone [https://github.com/tan-11/Dockerized-Big-Data-Resource-Manager](https://github.com/tan-11/Dockerized-Big-Data-Resource-Manager)
cd Dockerized-Big-Data-Resource-Manager
```

### Step 3: Build the Hadoop Base Image
```bash
docker build -t hadoop_container -f Dockerfile.hadoop .
```

### Step 4: Install Python Libraries
```bash
pip install -r requirements.txt
```

### Step 5: Configure Docker Permissions
Ensure the user running the app has permission to talk to the Docker Daemon:
```bash
sudo usermod -aG docker $USER
```

## 5. RUNNING THE APPLICATION
### 1. Start the Flask Middleware
Run the applications in the background:
```bash
sudo python3 app.py &
sudo python3 admin.py &
```

### 2. Access the Web Portal
Open your web browser and navigate to:
- User Site: http://localhost:5000
- Admin Site: http://localhost:7000

## 6. USAGE GUIDE
[Student Workflow]
1. Log in using student credentials.
2. Check "Host Status" on the dashboard to see available resources.
3. Enter desired resource limits (must be within Global Limits).
4. Click "Create Container".
5. Wait for the success message containing your IP, SSH Port, and SSH command line.
6. Connect via Terminal: copy and paste the provided SSH command.

[Super User Request]
1. If standard limits are insufficient (e.g., for AI/ML training), fill out the "Super User Request" form on the dashboard.
2. Wait for Administrator approval.
3. Once approved, launch the high-performance container.

[Administrator Workflow]
1. Log in via the Admin Login page.
2. Monitor "System Resources Overview" (Pie Charts).
3. View "Pending Resource Requests" to Approve/Reject Super User applications.
4. Use "Container Monitoring" to Stop/Kill zombies or abusive containers.
5. Manage "Global Limits" to set the hard cap for standard users.
6. Use "Storage Management" to view & delete storage of users.

## 7. FOLDER STRUCTURE
```text
/PowerDockerLab
├── app.py                 # Main Flask application entry point
├── admin.py               # Administrator routes and logic
├── utils.py               # Helper functions (Resource checks, locking)
├── templates/             # HTML files (Dashboard, Login, Admin)
├── user_data/             # Persistent storage mount points for users (created on first run)
├── entrypoint.sh          # Shell script for container startup initialization
├── Dockerfile.hadoop      # Docker configuration for Big Data nodes
├── docker_install.txt     # Docker installation guidance
├── requirements.txt       # Python dependencies
└── README.md              # This file
```
