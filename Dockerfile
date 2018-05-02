FROM ubuntu:16.04

RUN groupadd --gid 1000 user \
    && useradd --uid 1000 --gid user --shell /bin/bash --create-home user \
    && mkdir -p /etc/sudoers.d \
    && echo 'user ALL=(ALL:ALL) NOPASSWD:ALL' >> /etc/sudoers.d/user \
    && chmod 440 /etc/sudoers.d/user

RUN sed -i 's/archive.ubuntu.com/debian.linux.org.tw/' /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        sudo \
        make \
        g++ \
        python \
# for onnx
        git \
        protobuf-compiler \
        libprotoc-dev \
        python-pip \
        python-dev \
        python-setuptools \
    && rm -rf /var/lib/apt/lists/*

USER user

WORKDIR /home/user/onnc-runtime
RUN sudo chown user:user /home/user/onnc-runtime

COPY --chown=user:user ./ ./

RUN pip install onnx
