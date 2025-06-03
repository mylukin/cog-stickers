# cog-stickers

Make stickers with AI. Generates graphics with transparent backgrounds.

You can directly use this API: <https://replicate.com/fofr/sticker-maker>

# Requirements

- git
- docker
- [cog.run](https://cog.run/getting-started/)

# Quick Start

1. Clone code

```bash
git clone --recurse-submodules https://github.com/mylukin/cog-stickers.git
cd cog-stickers
```

2. Install cog (if not installed)

```bash
make install-cog
```

3. Build model

```bash
make build
```

4. Start server

```bash
make serve
```

The server is now running locally on port 5001.

# Available Commands

The project includes a Makefile with several useful commands:

```bash
make help         # Show all available commands
make install-cog  # Install cog binary (required for build)
make serve        # Start prediction server on port 5001
make shell        # Open bash shell in container
make logs         # Show container logs
make stop         # Stop all containers
make restart      # Restart the service
make status       # Show container status
make build        # Build model image
make push         # Push model to registry
make release      # Build and push model
```

# API Documentation

To view the OpenAPI schema, open localhost:5001/openapi.json in your browser or use cURL:

```bash
curl http://localhost:5001/openapi.json
```

# Reference

- <https://cog.run/getting-started/>
- <https://cog.run/http/>
