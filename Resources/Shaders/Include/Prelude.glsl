
// Trivial 2D rotation matrix, doesn't consider aspect ratio
mat2 rotate2d(float angle) {
    return mat2(cos(angle), -sin(angle), sin(angle), cos(angle));
}

// // Rotate around a point on any coordinate system
vec2 rotate2d(float angle, vec2 coord, vec2 anchor) {
    return rotate2d(angle) * (coord - anchor) + anchor;
}

// // Zoom

// Zoom into some point on an STUV coordinates
vec2 zoom(vec2 uv, float zoom, vec2 anchor) {
    return (uv - anchor) * (zoom*zoom) + anchor;
}

vec2 zoom(vec2 uv, float zoom) {
    return uv * (zoom*zoom);
}

// // Coordinates

// Converts a (0, 0) - (1, 1) coordinate to a (-1, -1) - (1, 1) coordinate
vec2 stuv2gluv(vec2 stuv) {
    return stuv * 2.0 - 1.0;
}

// Converts a (-1, -1) - (1, 1) coordinate to a (0, 0) - (1, 1) coordinate
vec2 gluv2stuv(vec2 gluv) {
    return (gluv + 1.0) / 2.0;
}
