#!/bin/bash

# 1. Start the SSH service in the background.
echo "--- Starting SSH Server ---"
/usr/sbin/sshd

# 2. Give the SSH service a moment to start up.
sleep 2

# 3. Now that SSH is running, start the Hadoop HDFS services.
#    This command uses SSH to start the daemons.
echo "--- Starting Hadoop HDFS ---"
$HADOOP_HOME/sbin/start-dfs.sh

# 4. Start Zookeeper (Kafka's dependency).
# The "-daemon" flag runs it in the background.
echo "--- Starting Zookeeper ---"
$KAFKA_HOME/bin/zookeeper-server-start.sh -daemon $KAFKA_HOME/config/zookeeper.properties

# 5. Give Zookeeper a moment to start up.
sleep 2

# 6. Start the Kafka Broker.
echo "--- Starting Kafka Server ---"
$KAFKA_HOME/bin/kafka-server-start.sh -daemon $KAFKA_HOME/config/server.properties

echo "--- All services started. Container is now running. ---"
echo "--- You can now SSH into the container. ---"

# 4. Keep the container running in the foreground.
#    This command will run forever, preventing the container from exiting.
tail -f /dev/null