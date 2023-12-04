
// Trivial 2D rotation matrix, doesn't consider aspect ratio
mat2 rotate2d(float angle) {
    return mat2(cos(angle), -sin(angle), sin(angle), cos(angle));
}

// // Rotate around a point on any coordinate system
vec2 rotate2d(float angle, vec2 coord, vec2 anchor) {
    return rotate2d(angle) * (coord - anchor) + anchor;
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


// // Utils

vec4 alpha_composite(vec4 a, vec4 b) {
    return a + b * (1.0 - a.a);
}

// A is proportional to B
// C is proportional to what?
// what = b*c / a for a \neq 0
float proportion(float a, float b, float c) {
    return (b * c) / a;
}

// Saturation
vec4 saturate(vec4 color, float amount) {return clamp(color * amount, 0.0, 1.0);}
vec3 saturate(vec3 color, float amount) {return clamp(color * amount, 0.0, 1.0);}
vec2 saturate(vec2 color, float amount) {return clamp(color * amount, 0.0, 1.0);}

// Vectors
vec2 polar(float radius, float angle) {
    return radius * vec2(cos(angle), sin(angle));
}

// Draws an image on the center considering its aspect ratio (stretches horizontally)
vec4 draw_image(sampler2D image, vec2 stuv) {
    vec2 resolution = textureSize(image, 0);
    vec2 scale = vec2(resolution.y / resolution.x, 1.0);
    vec2 gluv = stuv2gluv(stuv);
    gluv *= scale;
    return texture(image, gluv2stuv(gluv));
}

// // Zoom

// Zoom into some point on an STUV coordinates
vec2 zoom(vec2 uv, float zoom, vec2 anchor) {
    return (uv - anchor) * (zoom*zoom) + anchor;
}

vec2 zoom(vec2 uv, float zoom) {
    return uv * (zoom*zoom);
}
