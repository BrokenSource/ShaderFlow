// ---------------------------------------------|
// SombreroCamera definitions

#ifndef SOMBRERO_CAMERA
#define SOMBRERO_CAMERA

    // SombreroCamera Mode Enum
    #define SombreroCameraMode2D         0
    #define SombreroCameraModeSpherical  1
    #define SombreroCameraModeFreeSombreroCamera 2

    // SombreroCamera Projection Enum
    #define SombreroCameraProjectionPerspective     0
    #define SombreroCameraProjectionVirtualReality  1
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

        vec3 origin;  // Origin of the camera ray
        vec3 target;  // Target of the camera ray
        vec3 ray;     // SombreroCamera ray normalized vector

        //// Rays 2D

        vec2 screen;
        vec2 uv;             // UV coordinates of the 2D ray
        bool out_of_bounds;  // Out of bounds flag

        //// Virtual Reality
        float separation;

        //// Parameters
        float isometric;
        float fov;
        float orbital;
    };

    /* Builds a rectangle where the camera is looking at centered on the origin */
    vec3 SombreroCameraRectangle(SombreroCamera camera, float size) {
        return size*(camera.screen.y*camera.Z - camera.screen.x*camera.Y);
    }

    vec3 SombreroCameraRayOrigin(SombreroCamera camera) {
        return camera.position + SombreroCameraRectangle(camera, camera.fov*camera.isometric) - camera.X*camera.orbital;
    }

    vec3 SombreroCameraRayTarget(SombreroCamera camera) {
        return camera.position + SombreroCameraRectangle(camera, camera.fov) + camera.X * (1 - camera.orbital);
    }

    SombreroCamera SombreroCameraRay2D(SombreroCamera camera) {

        // Calculate the intersection with the x=1 plane
        // The equation is: origin + (t * direction) = (1, y, z)
        float t = (1 - camera.origin.x) / camera.ray.x;

        // The ray intersects the plane behind the camera
        if (t < 0) {
            camera.out_of_bounds = true;
            return camera;
        }

        // Calculate the intersection point
        vec3 intersection = camera.origin + (t*camera.ray);

        // Return the (y, z) components
        camera.uv = vec2(-intersection.y, intersection.z);

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
            vec3 separation = camera.Y * side*(camera.separation/2.0);
            camera.origin = SombreroCameraRayOrigin(camera) + separation;
            camera.target = SombreroCameraRayTarget(camera) + separation;

        // Equirectangular
        } else if (camera.projection == SombreroCameraProjectionEquirectangular) {
            camera.origin = camera.position;

            float phi   = PI*camera.screen.y/2;
            float theta = PI*camera.screen.x/iAspectRatio;
            vec3 target = camera.X;

            target = rotateAxis(target, -camera.Y, phi);
            target = rotateAxis(target, camera.Z, -theta);

            camera.target = camera.position + target;
        }

        // Origin and target rays projections
        camera.ray = normalize(camera.target - camera.origin);

        return SombreroCameraRay2D(camera);
    }

#endif

// ---------------------------------------------|
// SombreroCamera implementation

SombreroCamera iInitSombreroCamera(vec2 gluv) {
    SombreroCamera camera;
    camera.screen        = gluv;
    camera.mode          = iCameraMode;
    camera.projection    = iCameraProjection;
    camera.position      = iCameraPosition;
    camera.orbital       = iCameraOrbital;
    camera.UP            = iCameraUP;
    camera.X             = iCameraX;
    camera.Y             = iCameraY;
    camera.Z             = iCameraZ;
    camera.isometric     = iCameraIsometric;
    camera.fov           = iCameraFOV;
    camera.separation    = iCameraVRSeparation;
    camera.out_of_bounds = false;
    return camera;
}

// Get the Camera
SombreroCamera iCamera = iProjectSombreroCamera(iInitSombreroCamera(gluv));

