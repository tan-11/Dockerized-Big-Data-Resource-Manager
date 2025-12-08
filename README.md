# Dockerized Big Data Resource Manager

## Project Overview
This project is an On-Premise Cloud-like Resource Sharing Platform designed to provision isolated, resource-limited Big Data environments to multiple remote users on a single host machine.

The platform uses a Flask web application for managing user accounts, resource requests, and container lifecycle. It leverages Docker to create secure, dedicated sandboxes pre-configured with a Hadoop, Spark, and Kafka stack for each approved user.

## Features
- User/Admin Authentication: Separate secure login for general users and administrators.
- Resource-limited Creation System: Users can create specific CPU, RAM, and Disk space, with global resource limits adjusted by admin.
- Automated Container Provisioning: A dedicated Docker container is created with the requested resource limits.
- Resource-unlimied Super User requests: Users can request the CPU, RAM, and Disk space out of the limited bound, but only created after admin approved.
- Permanent Volumes: Each container is mounted a file space in host, it will retain even container has been deleted. It will be deleted only the user choose to delete it.
- Integrated Big Data Stack: Each user container is pre-installed and configured with:
  - Hadoop 3.3.1 (HDFS)
  - Apache Spark 3.2.1
  - Apache Kafka 3.1.0
- Secure SSH Access: Users can download an SSH private key from their dashboard to securely connect to their container.
- User Dashboard: Control container state (Start/Stop/Delete) and view current resource allocation.
- Admin Panel:
  - Set Global Resource Limits to prevent resource over-commitment.
  - Monitor all active containers and overall host resource utilization.
  - Approve or Reject pending super user resource requests.

## Technology Stack
| Component | Technology | Role |
| Backend Framework | Python | Web Application, User/Admin Logic, Container Management |
|Containerization | Docker | Isolation, Resource Limiting, Environment Setup |
| System Info	| psutil, sdutil | Monitoring host and container resources. |
| Frontend | HTML, CSS, Jinja2 | User Dashboard and Admin Control Panels. |

## Architecture and Flow
The application runs on a dedicated host machine, acting as the resource manager and Docker controller.
1. User Request: For limited-resources request, the user can create directly the container by sending the resources-demand (CPUs, RAM, MEMORY) in the limited bound. For super user request (out of bound resources), the user can requests by sending the resorces-demand (not exceed to host available resources) and waiting for admin approval.
2. Admin Approval: The Administrator approves the super user's request via the dedicated Admin Panel.
3. Container Provisioning: The Flask backend (utils.py) executes Docker commands to:
  - Create a new Docker container using the pre-built bigdata-user-env image (defined by Dockerfile.hadoop).
  - Set resource limits (CPU, RAM, MEMORY).
  - Generate a unique SSH key pair for the user and inject the public key into the container.
  - Set up a persistent Docker volume to store user data (/user_data/{username}).
  - Set up the big data stack
4. User Access: The user downloads their private key and connects securely via SSH to the exposed port of their specific container. The container's entrypoint.sh automatically starts HDFS, Spark, and Kafka on startup, providing an immediate working environment.

## Setup and Installation
### Prerequisites
- Host OS: Linux (Ubuntu/Debian recommended for Docker and shell scripts).
- Docker: Docker Engine installed and running. The user running the Flask app must have permissions to execute docker commands.
- Python: Python 3.x and pip.

## Usage
### Admin Access
1. Navigate to the Admin Login page (URL will depend on your host setup).
2. Default Credentials (Change for production):
  - Username: admin
  - Password: 123456
3. From the Admin Dashboard (admin.py routes):
  - Monitoring: View, Stop, Delete status of all running containers.
  - Requests: Approve or reject pending super user resource requests.
  - Settings: Set the Global Resource Limits for any single user.

### User Access
1. Register/Login: Create an account on the main application page.
2. Request Resources: Submit a request for the required CPU/RAM/Disk resources on the Dashboard page.
3. Wait for Approval (only super request): For super request, the request moves to a pending state until approved by the Admin.
4. Start Container & Download Key: Once approved or created, the system will provide a private key file (.pem) and ssh code.
5. SSH into Container: Downloaded key and copy & paste the ssh code to terminal (path of key may needs to change) to connect securely to the provisioned container. 
