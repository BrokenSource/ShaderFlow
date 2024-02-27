#ifndef SOMBRERO_CAMERA
#define SOMBRERO_CAMERA

    // SombreroCamera Mode Enum
    #define SombreroCameraModeFreeCamera 1
    #define SombreroCameraMode2D 2
    #define SombreroCameraModeSpherical 3

    // SombreroCamera Projection Enum
    #define SombreroCameraProjectionPerspective 0
    #define SombreroCameraProjectionVirtualReality 1
    #define SombreroCameraProjectionEquirectangular 2

    struct SombreroCamera {

        //// Basic

        int  mode;        // SombreroCamera mode, defined on by the SombreroCameraMode enum
        int  projection;  // SombreroCamera projection, defined on by the SombreroCameraProjection enum

        //// Position

        vec3 position;  // SombreroCamera position in world coordinates
        vec3 UP;        // SombreroCamera up vector
        vec3 X;         // SombreroCamera X axis
        vec3 Y;         // SombreroCamera Y axis
        vec3 Z;         // SombreroCamera Z axis

        //// Rays 3D

        vec3 origin;   // Origin of the camera ray
        vec3 target;   // Target of the camera ray
        vec3 ray;      // SombreroCamera ray normalized vector
        float orbital; // Displacement of origin and target from the position
        float dolly;   // Displacement of the origin from the position

        //// Rays 2D

        vec2 screen;
        vec2 uv;             // UV coordinates of the 2D ray
        vec2 gluv;
        vec2 agluv;
        vec2 stuv;
        vec2 astuv;
        bool out_of_bounds;  // Out of bounds flag

        //// Virtual Reality
        float separation;

        //// Parameters
        float isometric;
        float zoom;
    };

    /* Builds a rectangle where the camera is looking at centered on the origin */
    vec3 SombreroCameraRectangle(SombreroCamera camera, float size) {
        return size*(camera.screen.x*camera.X + camera.screen.y*camera.Y);
    }

    vec3 SombreroCameraRayOrigin(SombreroCamera camera) {
        return camera.position
            + SombreroCameraRectangle(camera, (1/camera.zoom)*camera.isometric)
            - (camera.Z*camera.orbital)
            - (camera.Z*camera.dolly);
    }

    vec3 SombreroCameraRayTarget(SombreroCamera camera) {
        return camera.position
            + SombreroCameraRectangle(camera, (1/camera.zoom))
            - (camera.Z*camera.orbital)
            + camera.Z;
    }

    SombreroCamera SombreroCameraRay2D(SombreroCamera camera) {

        // Calculate the intersection with the z=1 plane
        // The equation is: origin + (t * direction) = (x, y, 1)
        float t = (1 - camera.origin.z) / camera.ray.z;

        // The ray intersects the plane behind the camera
        if (t < 0) {
            camera.out_of_bounds = true;
            return camera;
        }

        // Calculate the intersection point
        camera.uv    = (camera.origin + (t*camera.ray)).xy;
        camera.gluv  = camera.uv;
        camera.stuv  = stuv2gluv(camera.uv);
        camera.agluv = vec2(camera.gluv.x/iAspectRatio, camera.gluv.y);
        camera.astuv = gluv2stuv(camera.agluv);
        return camera;
    }

    SombreroCamera iProjectSombreroCamera(SombreroCamera camera) {

        // Perspective - Simple origin and target
        if (camera.projection == SombreroCameraProjectionPerspective) {
            camera.origin = SombreroCameraRayOrigin(camera);
            camera.target = SombreroCameraRayTarget(camera);

        // Virtual Reality - Emulate two cameras, same as perspective
        } else if (camera.projection == SombreroCameraProjectionVirtualReality) {

            // Make both sides of the uv a new GLUV
            int side = (agluv.x <= 0 ? 1 : -1);
            camera.screen += side*vec2(iAspectRatio/2, 0);

            // Get the VR Horizontal Separation and add to the new own projections
            vec3 separation = camera.X * side*(camera.separation/2.0);
            camera.origin = SombreroCameraRayOrigin(camera) - separation;
            camera.target = SombreroCameraRayTarget(camera) - separation;

        // Equirectangular
        } else if (camera.projection == SombreroCameraProjectionEquirectangular) {
            camera.origin = camera.position;

            float phi   = PI*camera.screen.y/2;
            float theta = PI*camera.screen.x/iAspectRatio;
            vec3 target = camera.Z;

            target = rotateAxis(target, camera.X, -phi);
            target = rotateAxis(target, camera.Y, theta);

            camera.target = camera.position + target;
        }

        // Origin and target rays projections
        camera.ray = normalize(camera.target - camera.origin);

        return SombreroCameraRay2D(camera);
    }

#endif

// Initialization

SombreroCamera iInitSombreroCamera(vec2 gluv) {
    SombreroCamera camera;
    camera.screen        = gluv;
    camera.mode          = iCameraMode;
    camera.projection    = iCameraProjection;
    camera.position      = iCameraPosition;
    camera.orbital       = iCameraOrbital;
    camera.dolly         = iCameraDolly;
    camera.UP            = iCameraUP;
    camera.X             = iCameraX;
    camera.Y             = iCameraY;
    camera.Z             = iCameraZ;
    camera.isometric     = iCameraIsometric;
    camera.zoom          = iCameraZoom;
    camera.separation    = iCameraVRSeparation;
    camera.out_of_bounds = false;
    return camera;
}

SombreroCamera iCamera = iProjectSombreroCamera(iInitSombreroCamera(gluv));

