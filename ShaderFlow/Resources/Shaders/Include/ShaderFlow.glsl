#ifndef ShaderFlowSpecification
#define ShaderFlowSpecification

// ------------------------------------------------------------------------------------------------|
// The Good Code - A Sane Attempt

#define iFrameTime   (1/iFrameRate)
#define iDeltaTime   (iFrameTime)
#define iTau         (iTime/max(iDuration, iFrameTime))
#define iAspectRatio (float(iResolution.x)/iResolution.y)
#define iRendering   (!iRealtime)

const float PI    = 3.1415926535897932;
const float TAU   = 6.2831853071795864;
const float SQRT2 = 1.4142135623730951;
const float SQRT3 = 1.7320508075688772;

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
// • Positive difference gives min(a, b) else max(a, b)
float smoothlerp(float a, float b, float difference) {
    float t = clamp((a-b)/difference + 0.5, 0, 1);
    float offset = difference*t*(1-t)/2;
    return mix(a, b, t) - offset;
}

// Aliases to smoothlerp, smooth versions of min and max
float smin(float a, float b, float k) {return smoothlerp(a, b,  k);}
float smax(float a, float b, float k) {return smoothlerp(a, b, -k);}
float smin(float a, float b) {return smin(a, b, 1);}
float smax(float a, float b) {return smax(a, b, 1);}

// Smoothstep linear interpolation between two values
// • Useful when a=f(x), b=f(x) and the transition is [x0, x1]
float smoothmix(float a, float b, float x0, float x1, float x) {
    return mix(a, b, smoothstep(x0, x1, x));
}

// Aliases to smoothmix, smooth versions of mix
float smix(float a, float b, float x0, float x1, float x) {
    return smoothmix(a, b, x0, x1, x);
}

// // Angles and Rotations

// Angle between two vectors for any dimensions
float angle(vec4 A, vec4 B) {return acos(dot(A, B) / (length(A)*length(B)));}
float angle(vec3 A, vec3 B) {return acos(dot(A, B) / (length(A)*length(B)));}
float angle(vec2 A, vec2 B) {return acos(dot(A, B) / (length(A)*length(B)));}

// Trivial 2D rotation matrix, doesn't consider aspect ratio
mat2 rotate2d(float angle) {
    return mat2(cos(angle), -sin(angle), sin(angle), cos(angle));
}

#define rotate2deg(angle) rotate2d(radians(angle))

// Rotate a vector around an axis, right-handed
vec3 rotate3d(vec3 vector, vec3 axis, float angle) {
    return mix(dot(axis, vector)*axis, vector, cos(angle)) + cross(axis, vector)*sin(angle);
}

#define rotate3deg(vector, axis, angle) rotate3d(vector, axis, radians(angle))

// // Coordinates conversion

// Converts a (0, 0) - (1, 1) coordinate to a (-1, -1) - (1, 1) coordinate
vec2 stuv2gluv(vec2 stuv) {return (stuv*2) - 1;}
vec2 s2g(vec2 stuv) {return stuv2gluv(stuv);}

// Converts a (-1, -1) - (1, 1) coordinate to a (0, 0) - (1, 1) coordinate
vec2 gluv2stuv(vec2 gluv) {return (gluv + 1)/2;}
vec2 g2s(vec2 gluv) {return gluv2stuv(gluv);}

// Applies or reverts Aspect Ratio to a (-1, -1) - (1, 1) coordinate
vec2 agluv2gluv(vec2 agluv) {return agluv * vec2(iAspectRatio, 1);}
vec2 gluv2agluv(vec2 gluv) {return gluv / vec2(iAspectRatio, 1);}

// Converts a (0, 0) - (1, 1) coordinate to a (0, 0) - (width, height) coordinate
vec2 stuv2stxy(vec2 stuv, vec2 resolution) {return resolution*stuv;}
vec2 stuv2stxy(vec2 stuv) {return stuv2stxy(stuv, iResolution);}

// Converts a (0, 0) - (width, height) coordinate to a (0, 0) - (1, 1) coordinate
vec2 stxy2stuv(vec2 stxy, vec2 resolution) {return stxy/resolution;}
vec2 stxy2stuv(vec2 stxy) {return stxy2stuv(stxy, iResolution);}

// Applies or reverts Aspect Ratio to a (0, 0) - (1, 1) coordinate
vec2 astuv2stuv(vec2 astuv) {
    return vec2(astuv.x*iAspectRatio + (1 - iAspectRatio)/2, astuv.y);
}
vec2 stuv2astuv(vec2 stuv) {
    return vec2((stuv.x - (1 - iAspectRatio)/2)/iAspectRatio, stuv.y);
}

// Out of Bounds checks
bool astuv_oob(vec2 astuv) {
    return (astuv.x<0)||(astuv.x>1)||(astuv.y<0)||(astuv.y>1);
}
bool stuv_oob(vec2 stuv) {
    return astuv_oob(stuv2astuv(stuv));
}
bool agluv_oob(vec2 agluv) {
    return (agluv.x<-1)||(agluv.x>1)||(agluv.y<-1)||(agluv.y>1);
}
bool gluv_oob(vec2 gluv) {
    return agluv_oob(gluv2agluv(gluv));
}

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

// // Textures

vec4 gtexture(sampler2D image, vec2 gluv) {
    vec2 resolution = textureSize(image, 0);
    vec2 scale = vec2(resolution.y/resolution.x, 1);
    return texture(image, gluv2stuv(gluv*scale));
}

vec4 agtexture(sampler2D image, vec2 agluv) {
    return gtexture(image, agluv2gluv(agluv));
}

vec4 stexture(sampler2D image, vec2 stuv) {
    return gtexture(image, stuv2gluv(stuv));
}

vec4 astexture(sampler2D image, vec2 astuv) {
    return agtexture(image, stuv2gluv(astuv));
}

#define draw_image stexture

// // Palettes

vec3 palette(float t, vec3 A, vec3 B, vec3 C, vec3 D) {
    if (t < 0.25) {
        return mix(A, B, t*4);
    } else if (t < 0.5) {
        return mix(B, C, (t - 0.25)*4);
    } else {
        return mix(C, D, (t - 0.5)*4);
    }
}

#define PALETTE_MAGMA_1 vec3(0.01060815, 0.01808215, 0.10018654)
#define PALETTE_MAGMA_2 vec3(0.38092887, 0.12061482, 0.32506528)
#define PALETTE_MAGMA_3 vec3(0.79650140, 0.10506637, 0.31063031)
#define PALETTE_MAGMA_4 vec3(0.95922872, 0.53307513, 0.37488950)
#define palette_magma(x) palette(x, PALETTE_MAGMA_1, PALETTE_MAGMA_2, PALETTE_MAGMA_3, PALETTE_MAGMA_4)


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

// SDF: Signed Distance Function

// SDF distance to a sphere at some position and radius
float sdSphere(vec3 origin, vec3 position, float radius) {
    return length(position - origin) - radius;
}

// SDF to a plane defined by a point and a normal
float sdPlane(vec3 origin, vec3 point, vec3 normal) {
    return dot(origin - point, normalize(normal));
}

// SDF to a box defined by a point and a size
float sdBox(vec3 origin, vec3 point, vec3 size) {
    vec3 d = abs(origin - point) - size/2;
    return min(max(d.x, max(d.y, d.z)), 0) + length(max(d, 0));
}

// SDF to a Octahedron defined by a point and a size
float sdOctahedron(vec3 origin, vec3 point, float size) {
    vec3 p = abs(origin - point);
    return (p.x + p.y + p.z - size) * SQRT3;
}

// Operators

// Union of two SDFs: Join two SDFs into one
float sdUnion(float a, float b) {
    return min(a, b);
}

// Smooth union of two SDFs: "Simple relative interpolation"
// • width defines the relative value range of the transition
float sdSmoothUnion(float a, float b, float width) {
    float k = clamp(0.5 + 0.5*(b-a)/width, 0, 1);
    return mix(b, a, k) - width*k*(1 - k);
}

// Subtraction of two SDFs: Get the difference between A and B
float sdSubtraction(float a, float b) {
    return max(-a, b);
}

// Smooth subtraction of two SDFs: "
// • width defines the relative value range of the transition
float sdSmoothSubtraction(float a, float b, float width) {
    float k = clamp(0.5 - 0.5*(b+a)/width, 0, 1);
    return mix(b, -a, k) + width*k*(1 - k);
}

// Intersection of two SDFs: Get where two SDFs meet
float sdIntersection(float a, float b) {
    return max(a, b);
}

// Smooth intersection of two SDFs: "Opposite of union, so k' = 1 - k"
// • width defines the relative value range of the transition
float sdSmoothIntersection(float a, float b, float width) {
    float k = clamp(0.5 - 0.5*(b-a)/width, 0, 1);
    return mix(b, a, k) + width*k*(1 - k);
}

// ------------------------------------------------------------------------------------------------|
// The Bad Code - Accumulated Tech Debt

// // Utils

vec4 alpha_composite(vec4 a, vec4 b) {
    return a*(1 - b.a) + (b * b.a);
}

// Saturation
vec4 saturate(vec4 color, float amount) {return clamp(color * amount, 0, 1);}
vec3 saturate(vec3 color, float amount) {return clamp(color * amount, 0, 1);}
vec2 saturate(vec2 color, float amount) {return clamp(color * amount, 0, 1);}

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
        default: rgb = vec3(0);
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
