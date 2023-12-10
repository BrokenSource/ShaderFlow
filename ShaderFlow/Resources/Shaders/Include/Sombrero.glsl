
// Trivial 2D rotation matrix, doesn't consider aspect ratio
mat2 rotate2d(float angle) {
    return mat2(cos(angle), -sin(angle), sin(angle), cos(angle));
}

// Rotate around a point on any coordinate system
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
    return a*(1.0 - b.a) + (b * b.a);
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

vec3 spherical(float radius, float theta, float phi) {
    return vec3(
        radius * sin(theta) * cos(phi),
        radius * sin(theta) * sin(phi),
        radius * cos(theta)
    );
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

// // Math

float PI  = 3.1415926535897932384626433832795;
float TAU = 2 * PI;

float atan2(float y, float x) {
    if (y < 0) {
        return (2 * PI) - atan(-y, x);
    } else {
        return atan(y, x);
    }
}

float atan_normalized(float y, float x) {
    return atan(y, x) / PI;
}

float atan_normalized(vec2 point) {
    return atan_normalized(point.y, point.x);
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






// ------------------------------------------------------------------------------------------------|

// Fixme: Move Camera stuff on a SombreroCamera include file and better comments

vec3 iCameraRectangle(float size, vec2 auv) {
    return size * (auv.y*iCameraZ - auv.x*iCameraY);
}

vec3 iCameraRayOrigin(vec2 auv) {
    return iCameraPosition + iCameraRectangle(iCameraFOV*iCameraIsometric, auv);
}

vec3 iCameraRayTarget(vec2 auv) {
    return iCameraPosition + iCameraRectangle(iCameraFOV, auv) + iCameraX;
}

vec3 iCameraRayNormal(vec2 auv) {
    return normalize(iCameraRayTarget(auv) - iCameraRayOrigin(auv));
}

/**
 * Returns the (x, z) coordinates of the intersection of the ray with the x=1 plane
 * The third component says 1 for "forward" intersections and -1 for intersections behind the camera
 */
vec3 iCameraRayUV(vec3 origin, vec3 target) {
    vec3 normal = normalize(target - origin);

    // Calculate the intersection with the x=1 plane
    // The equation is: origin + (t * direction) = (1, y, z)
    float t = (1 - origin.x) / normal.x;

    // They ray intersects the plane behind the camera
    if (t < 0) {return vec3(0, 0, -1);}

    // Calculate the intersection point
    vec3 intersection = origin + (t * normal);

    // Return the (x, z) components
    return vec3(-intersection.y, intersection.z, 1.0);
}

vec3 iCameraUV() {
    vec3 origin;
    vec3 target;
    vec2 uv = gluv;

    // Perspective
    if (iCameraProjection == 0) {
        origin = iCameraRayOrigin(uv);
        target = iCameraRayTarget(uv);

    // Equirectangular
    }else if (iCameraProjection == 2) {
        vec3 sphere = spherical(1.0, agluv.x*PI, agluv.y*PI/2);
        target = sphere - iCameraPosition;
        origin = iCameraPosition;

    // Perspective (+Virtual Reality)
    } else if (iCameraProjection == 1) {

        // Make both sides of the screen a new GLUV
        float side = (agluv.x <= 0 ? 1 : -1);
        uv += side*vec2(iAspectRatio/2, 0.0);

        // Get the VR Horizontal Separation and add to the new own projections
        vec3 separation = iCameraY * side*(iCameraVRSeparation/2.0);
        origin = iCameraRayOrigin(uv) + separation;
        target = iCameraRayTarget(uv) + separation;
    }

    // Make the projections
    return iCameraRayUV(origin, target);
}