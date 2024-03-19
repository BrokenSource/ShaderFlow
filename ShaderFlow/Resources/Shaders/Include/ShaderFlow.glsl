#ifndef ShaderFlowSpecification
#define ShaderFlowSpecification

// ------------------------------------------------------------------------------------------------|
// The Good Code - A Sane Attempt

#define iFrameTime   (1.0/iFrameRate)
#define iDeltaTime   iFrameTime
#define iTau         (iTime/max(iDuration, iFrameTime))
#define iAspectRatio (float(iResolution.x)/iResolution.y)
#define iRendering   (!iRealtime)

float PI  = 3.1415926535897932384626433832795;
float TAU = 2.0 * PI;

// // Interpolation

// Interpolate between two points (x0, y0) and (x1, y1) at x
float lerp(float x0, float y0, float x1, float y1, float x) {
    return y0 + (x - x0)*(y1 - y0)/(x1 - x0);
}

// Your standard "Cross Multiplication", (a/c) = (b/?), returns '?'
float proportion(float a, float b, float c) {
    return (b*c)/a;
}

// Smooth relative interpolation between two values given a magnitude difference factor
// • Applied whenever |b - a| > difference
// • Positive difference gives min(a, b)
float smoothlerp(float a, float b, float difference) {
    float t = clamp((a-b)/difference + 0.5, 0.0, 1.0);
    float offset = difference*t*(1-t)/2;
    return mix(a, b, t) - offset;
}

// Aliases to smoothlerp, smooth versions of min and max
float smin(float a, float b, float k) {return smoothlerp(a, b,  k);}
float smax(float a, float b, float k) {return smoothlerp(a, b, -k);}
float smin(float a, float b) {return smin(a, b, 1);}
float smax(float a, float b) {return smax(a, b, 1);}

// // Angles and Rotations

// Angle between two vectors for any dimensions
float angle(vec4 A, vec4 B) {return acos(dot(A, B) / (length(A)*length(B)));}
float angle(vec3 A, vec3 B) {return acos(dot(A, B) / (length(A)*length(B)));}
float angle(vec2 A, vec2 B) {return acos(dot(A, B) / (length(A)*length(B)));}

// Trivial 2D rotation matrix, doesn't consider aspect ratio
mat2 rotate2d(float angle) {
    return mat2(cos(angle), -sin(angle), sin(angle), cos(angle));
}

// Rotate around a point on any coordinate system
vec2 rotate2d(float angle, vec2 coord, vec2 anchor) {
    return rotate2d(angle) * (coord - anchor) + anchor;
}

// Rotate a vector around an axis, right-handed
vec3 rotateAxis(vec3 vector, vec3 axis, float angle) {
    return vector*cos(angle) + cross(axis, vector)*sin(angle) + axis*dot(axis, vector)*(1 - cos(angle));
}

// // Coordinates conversion

// Converts a (0, 0) - (1, 1) coordinate to a (-1, -1) - (1, 1) coordinate
vec2 stuv2gluv(vec2 stuv) {return stuv * 2.0 - 1.0;}
vec2 s2g(vec2 stuv) {return stuv2gluv(stuv);}

// Converts a (-1, -1) - (1, 1) coordinate to a (0, 0) - (1, 1) coordinate
vec2 gluv2stuv(vec2 gluv) {return (gluv + 1.0) / 2.0;}
vec2 g2s(vec2 gluv) {return gluv2stuv(gluv);}

// Get a polar coordinate from (r, θ)
vec2 polar2rect(float radius, float angle) {
    return radius * vec2(cos(angle), sin(angle));
}

// Get a Rectangular coordinate from a Spherical coordinate (radius, θ, φ)
vec3 sphere2rect(float radius, float theta, float phi) {
    return vec3(
        radius*sin(theta)*cos(phi),
        radius*sin(theta)*sin(phi),
        radius*cos(theta)
    );
}

// Draws an image on the center considering its aspect ratio (stretches horizontally)
vec4 draw_image(sampler2D image, vec2 stuv) {
    vec2  resolution = textureSize(image, 0);
    vec2  scale = vec2(resolution.y/resolution.x, 1.0);
    vec2  gluv  = stuv2gluv(stuv);
    return texture(image, gluv2stuv(gluv*scale));
}

// // Palettes

vec3 palette(float t, vec3 A, vec3 B, vec3 C, vec3 D) {
    if (t < 0.25) {
        return mix(A, B, t * 4.0);
    } else if (t < 0.5) {
        return mix(B, C, (t - 0.25) * 4.0);
    } else {
        return mix(C, D, (t - 0.5) * 4.0);
    }
}

// // Piano and Midi Keys

// Black keys have a constant index relative to the octave
bool isBlackKey(int index) {
    int key = index % 12;
    return key==1||key==3||key==6||key==8||key==10;
}
bool isBlackKey(float key) {
    return isBlackKey(int(key));
}

// Can only be black or white
bool isWhiteKey(int index) {
    return !isBlackKey(index);
}
bool isWhiteKey(float key) {
    return isWhiteKey(int(key));
}

// // Ray Marching

// Safest distance to a sphere at some position and radius
float sdSphere(vec3 origin, vec3 position, float radius) {
    return length(position - origin) - radius;
}

// Safest distance to a plane defined by a point and a normal
float sdPlane(vec3 origin, vec3 point, vec3 normal) {
    return dot(origin - point, normal);
}

// ------------------------------------------------------------------------------------------------|
// The Bad Code - Accumulated Tech Debt

// // Utils

vec4 alpha_composite(vec4 a, vec4 b) {
    return a*(1.0 - b.a) + (b * b.a);
}

// Saturation
vec4 saturate(vec4 color, float amount) {return clamp(color * amount, 0.0, 1.0);}
vec3 saturate(vec3 color, float amount) {return clamp(color * amount, 0.0, 1.0);}
vec2 saturate(vec2 color, float amount) {return clamp(color * amount, 0.0, 1.0);}

// // Zoom

// Zoom into some point on an STUV coordinates
vec2 zoom(vec2 uv, float zoom, vec2 anchor) {
    return (uv - anchor) * (zoom*zoom) + anchor;
}

vec2 zoom(vec2 uv, float zoom) {
    return uv * (zoom*zoom);
}

// // Math
float atan_normalized(float x) {
    return 2 * atan(x) / PI;
}

float atan1(vec2 point) {
    return atan(point.y, point.x);
}

float atan1_normalized(vec2 point) {
    return atan(point.y, point.x) / PI;
}

float atan2(float y, float x) {
    if (y < 0) {
        return TAU - atan(-y, x);
    } else {
        return atan(y, x);
    }
}

float atan2(vec2 point) {
    return atan2(point.y, point.x);
}

float atan2_normalized(float y, float x) {
    return atan2(y, x) / PI;
}

float atan2_normalized(vec2 point) {
    return atan2_normalized(point.y, point.x);
}

// // Colors

// https://www.rapidtables.com/convert/color/hsv-to-rgb.html
// "Assume 0 <= H < 2pi, 0 <= S <= 1, 0 <= V <= 1"
vec3 hsv2rgb(vec3 hsv) {
    float h = hsv.x;
    float s = hsv.y;
    float v = hsv.z;
    h = mod(h, 2*PI);
    float c = v * s;
    float x = c * (1 - abs(mod(h / (PI/3), 2) - 1));
    float m = v - c;
    vec3 rgb = vec3(0.5);
    switch (int(floor(6*(h/(2*PI))))) {
        case 0: rgb = vec3(c, x, 0); break;
        case 1: rgb = vec3(x, c, 0); break;
        case 2: rgb = vec3(0, c, x); break;
        case 3: rgb = vec3(0, x, c); break;
        case 4: rgb = vec3(x, 0, c); break;
        case 5: rgb = vec3(c, 0, x); break;
        default: rgb = vec3(0.0);
    }
    return rgb + vec3(m);
}

vec4 hsv2rgb(vec4 hsv) {
    return vec4(hsv2rgb(hsv.rgb), hsv.a);
}


// // Noise

float noise21(vec2 coords) {
   return fract(sin(dot(coords.xy, vec2(18.4835183, 59.583596))) * 39758.381532);
}

float noise11(float f) {
   return fract(sin(f) * 39758.381532);
}

#endif
