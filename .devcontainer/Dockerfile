FROM osrf/ros:jazzy-desktop-full

SHELL ["/bin/bash", "-c"]

RUN apt-get update && apt-get install -y \
    git \
    python3-pip \
    python3-colcon-common-extensions \
    python3-rosdep \
    ros-jazzy-rviz2 \
    ros-jazzy-moveit \
    && rm -rf /var/lib/apt/lists/*

RUN echo "source /opt/ros/jazzy/setup.bash" >> /root/.bashrc

WORKDIR /workspaces/GadgetInspectra