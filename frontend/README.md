# Frontend (Leaflet + Three.js skeleton)

This folder contains a minimal frontend skeleton demonstrating a Leaflet map with a Three.js overlay.

How to use

- Open `frontend/index.html` in a browser (or build the Docker image) to see the map and a demo 3D cube.
- The example uses CDNs for Leaflet and Three.js for a quick prototype.

Docker

Build and run the frontend container (from repository root):

```bash
docker build -t p3-frontend:local frontend/
docker run --rm -p 8080:80 p3-frontend:local
# then open http://localhost:8080
```

Notes

- This is a minimal skeleton; for production consider vendoring libraries, pinning versions, and adding tests.
