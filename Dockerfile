FROM ghcr.io/railwayapp/nixpacks:ubuntu

# Install git (in case not already installed)
RUN apt-get update && apt-get install -y git

# Install nixpacks
RUN curl -sSL https://nixpacks.com/install.sh | bash

# Ensure nixpacks is available
ENV PATH="/usr/local/bin:$PATH"

# Fetch the .git folder
RUN git init \
    && git remote add origin https://github.com/virginviolet/sponsorblockcasino.git \
    && git fetch --depth=1 origin main \
    && git checkout -f main
RUN ls -a

# Initialize and update submodules
RUN git submodule update --init --recursive

RUN rm -rf .git
RUN rm -rf sponsorblockchain/.git

# Set working directory to /app
WORKDIR /app

# Copy everything downloaded from the repo into /app
COPY . /app

# Initialize and update submodules
RUN git init && git submodule update --init --recursive

# Generate .nixpacks files locally
RUN nixpacks build --name temp-build /app

# Install Nix dependencies
RUN nix-env -if .nixpacks/*.nix && nix-collect-garbage -d

# Install Python dependencies with nixpacks's default method
RUN python -m venv --copies /opt/venv && . /opt/venv/bin/activate && \
pip install -r requirements.txt

# Add the virtual environment to PATH
RUN printf '\nPATH=/opt/venv/bin:$PATH' >>/root/.profile

# Copy project files last
COPY . /app/.

# Default command
CMD ["python", "sponsorblockcasino.py"]
