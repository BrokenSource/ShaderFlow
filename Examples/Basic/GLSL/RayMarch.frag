/*
// (c) MIT, Tremeschin
*/

#define MAX_STEPS 100
#define MAX_DIST 100.0
#define MIN_DIST 0.001

float sdScene(vec3 origin) {
    // origin = fract(origin) - 0.5;

    // float sphere = sdSphere(origin, vec3(sin(iTime)*3, 0, 3), 1);
    // float box    = sdBox(origin, vec3(0, 0, 10), vec3(8));
    // float ground = sdPlane(origin, vec3(0, -1, 0), vec3(0, 1, 0));

    // float sdf = 1e10;
    // sdf = sdSmoothUnion(sdf, sphere, 1);
    // sdf = sdSmoothUnion(sdf, box, 1);
    // sdf = sdSmoothUnion(sdf, ground, 1);
    // return box;


    float sdf = 2*MAX_DIST;

    for (int i=2; i<8; i++) {
        sdf = sdUnion(sdf, sdBox(origin, vec3(0, 0, i), vec3(i-1)));
    }

    return sdf;

}

void main() {
    iCameraInit();
    vec3 col = vec3(0);

    // Camera setup
    vec3 origin = iCamera.origin;
    vec3 target = iCamera.target;
    vec3 forward = normalize(target - origin);

    // Raymarching
    float traveled = 0;
    float walk = 0;
    int steps;

    for (steps=0; steps<MAX_STEPS; steps++) {
        vec3 point = origin + (forward*traveled);
        walk       = sdScene(point);
        traveled  += walk;
        if (walk<MIN_DIST || walk>MAX_DIST) break;
    }

    // Color based on the distance
    // col = palette_magma(1 - (sqrt(traveled)*0.1 + steps*0.01));
    // col = vec3(sqrt(traveled)*0.1);
    col = vec3(1 - sqrt(steps)*0.1);

    fragColor = vec4(col, 1);
}