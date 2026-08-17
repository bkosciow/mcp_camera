# API Reference

Base URL: `http://localhost:8579`

## Authentication

All endpoints **except** `GET /health` require a bearer token:

```
Authorization: Bearer <CAMERA_AUTH_TOKEN>
```

The token comes from the service's `.env` (or environment). Requests without a valid token receive:

**401 Unauthorized**

```json
{
  "detail": "Invalid or missing token"
}
```

---

## GET /capture

Capture a fresh image from the first USB camera (index 0).

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
curl -H "Authorization: Bearer $CAMERA_AUTH_TOKEN" http://localhost:8579/capture > photo.jpg
curl -H "Authorization: Bearer $CAMERA_AUTH_TOKEN" "http://localhost:8579/capture?max_width=640" > photo_small.jpg
```

**404 Not Found** — No cameras detected

```json
{
  "error": "Camera not found"
}
```

**503 Service Unavailable** — Camera unavailable

```json
{
  "error": "Camera not connected",
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

## GET /capture/{cam_index}

Capture a fresh image from a specific camera.

### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `cam_index` | integer | Camera index (0-based) |

### Query Parameters

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `max_width` | integer | `1280` | `160`–`3840` | Maximum image width in pixels |

### Responses

**200 OK** — JPEG image captured successfully

```bash
curl -H "Authorization: Bearer $CAMERA_AUTH_TOKEN" http://localhost:8579/capture/1 > photo_cam2.jpg
curl -H "Authorization: Bearer $CAMERA_AUTH_TOKEN" "http://localhost:8579/capture/1?max_width=640" > photo_cam2_small.jpg
```

**404 Not Found** — Camera index doesn't exist

```json
{
  "error": "Camera not found"
}
```

**503 Service Unavailable** — Camera unavailable

```json
{
  "error": "Camera not connected",
  "code": "CAMERA_UNAVAILABLE"
}
```

---

## GET /camera

Get info for all detected cameras.

Returns a list of connected cameras with their device paths, connection state, current resolution, and available resolutions.

### Responses

**200 OK** — Camera list

```json
{
  "count": 2,
  "cameras": [
    {
      "index": 0,
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
    },
    {
      "index": 1,
      "connected": true,
      "device": "/dev/video1",
      "current_resolution": {
        "width": 1920,
        "height": 1080
      },
      "available_resolutions": [
        { "width": 640, "height": 480 },
        { "width": 1280, "height": 720 },
        { "width": 1920, "height": 1080 }
      ]
    }
  ]
}
```

**No cameras detected:**

```json
{
  "count": 0,
  "cameras": []
}
```

```bash
curl -H "Authorization: Bearer $CAMERA_AUTH_TOKEN" http://localhost:8579/camera
```

---

## GET /camera/{cam_index}

Get info for a specific camera.

### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `cam_index` | integer | Camera index (0-based) |

### Responses

**200 OK** — Camera info

```json
{
  "index": 0,
  "connected": true,
  "device": "/dev/video0",
  "current_resolution": {
    "width": 1280,
    "height": 720
  },
  "available_resolutions": [
    { "width": 640, "height": 480 },
    { "width": 1280, "height": 720 }
  ]
}
```

**404 Not Found** — Camera index doesn't exist

```json
{
  "error": "Camera 1 not found"
}
```

```bash
curl -H "Authorization: Bearer $CAMERA_AUTH_TOKEN" http://localhost:8579/camera/1
```

---

## GET /health

Check service and camera health.

Returns service status including all camera connection states, uptime, and any recent errors.

### Responses

**200 OK** — Health status (multiple cameras)

```json
{
  "status": "ok",
  "cameras": [
    { "index": 0, "connected": true, "device": "/dev/video0" },
    { "index": 1, "connected": true, "device": "/dev/video1" }
  ],
  "camera_count": 2,
  "uptime_seconds": 1234.5,
  "last_error": null
}
```

**Field descriptions:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `"ok"` if any camera connected, `"degraded"` if none |
| `cameras` | array | List of detected cameras with index, connection state, device |
| `camera_count` | integer | Number of detected cameras |
| `uptime_seconds` | number | Seconds since service started |
| `last_error` | string \| null | Last error message (from first camera), or null |

```bash
curl http://localhost:8579/health
```

**When no cameras are connected:**

```json
{
  "status": "degraded",
  "cameras": [],
  "camera_count": 0,
  "uptime_seconds": 567.8,
  "last_error": null
}
```
