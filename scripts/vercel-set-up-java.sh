#!/bin/bash
# Install OpenJDK
apt-get update && apt-get install -y openjdk-17-jdk

# Optional: verify Java installation
java -version