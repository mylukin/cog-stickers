# cog-stickers

Make stickers with AI. Generates graphics with transparent backgrounds.

You can directly use this API: <https://replicate.com/fofr/sticker-maker>

# Requirements

- git
- docker
- [cog.run](https://cog.run/getting-started/)

# Run

1. clone code

```bash
git clone --recurse-submodules https://github.com/mylukin/cog-stickers.git
cd cog-stickers
```

2. build model

```bash
cog build -t sticker-maker
```

3. run in docker

```bash
# If your model uses a CPU:
docker run -d -p 5001:5000 sticker-maker

# If your model uses a GPU:
docker run -d -p 5001:5000 --gpus all sticker-maker

# If you're on an M1 Mac:
docker run -d -p 5001:5000 --platform=linux/amd64 sticker-maker
```

The server is now running locally on port 5001.

To view the OpenAPI schema, open localhost:5001/openapi.json in your browser or use cURL to make requests:

```bash
curl http://localhost:5001/openapi.json
```

# Reference

- <https://cog.run/getting-started/>
- <https://cog.run/http/>
