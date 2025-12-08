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
