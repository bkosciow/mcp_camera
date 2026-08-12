# API Reference

Base URL: `http://localhost:8579`

---

## GET /capture

Capture a fresh image from the USB camera.

Returns a JPEG image resized to the specified max width. Every request captures a new frame — no caching.

### Query Parameters

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `max_width` | integer | `1280` | `160`–`3840` | Maximum image width in pixels |

### Responses

**200 OK** — JPEG image captured successfully

- `Content-Type`: `image/jpeg`
- Body: Raw JPEG bytes

```bash
curl http://localhost:8579/capture > photo.jpg
curl "http://localhost:8579/capture?max_width=640" > photo_small.jpg
```

**503 Service Unavailable** — Camera not available

```json
{
  "error": "No camera available",
  "code": "CAMERA_UNAVAILABLE"
}
```

**422 Unprocessable Entity** — Invalid query parameter

```json
{
  "detail": [
    {
      "loc": ["query", "max_width"],
      "msg": "Ensure this value is less than or equal to 3840",
      "type": "value_number.le"
    }
  ]
}
```

---

## GET /camera

Get camera info and available resolutions.

Probes the camera to discover which resolutions it actually supports. Useful for finding the best native quality your hardware can produce.

### Responses

**200 OK** — Camera info

```json
{
  "connected": true,
  "device": "/dev/video0",
  "current_resolution": {
    "width": 1280,
    "height": 720
  },
  "available_resolutions": [
    { "width": 640, "height": 480 },
    { "width": 800, "height": 600 },
    { "width": 1280, "height": 720 }
  ]
}
```

When camera is disconnected:

```json
{
  "connected": false,
  "device": null,
  "current_resolution": null,
  "available_resolutions": []
}
```

```bash
curl http://localhost:8579/camera
```

---

## GET /health

Check service and camera health.

Returns service status including camera connection state, uptime, and any recent errors.

### Responses

**200 OK** — Health status

```json
{
  "status": "ok",
  "camera": {
    "connected": true,
    "device": 0
  },
  "uptime_seconds": 1234.5,
  "last_error": null
}
```

**Field descriptions:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `"ok"` if camera connected, `"degraded"` if not |
| `camera.connected` | boolean | Whether camera is currently connected |
| `camera.device` | integer \| string \| null | The detected camera device (index or path) |
| `uptime_seconds` | number | Seconds since service started |
| `last_error` | string \| null | Last error message, or null if no error |

```bash
curl http://localhost:8579/health
```

**When camera is disconnected:**

```json
{
  "status": "degraded",
  "camera": {
    "connected": false,
    "device": null
  },
  "uptime_seconds": 567.8,
  "last_error": "No camera found"
}
```
