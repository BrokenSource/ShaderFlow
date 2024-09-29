#ifndef SHADERFLOW_CAMERA
#define SHADERFLOW_CAMERA

    // Camera Mode Enum
    #define CameraModeFreeCamera 0
    #define CameraMode2D 1
    #define CameraModeSpherical 2

    // Camera Projection Enum
    #define CameraProjectionPerspective 0
    #define CameraProjectionVirtualReality 1
    #define CameraProjectionEquirectangular 2

    struct Camera {

        //// Basic

        int mode;        // Camera mode, defined on by the CameraMode enum
        int projection;  // Camera projection, defined on by the CameraProjection enum

        //// Position

        vec3 position;  // Camera position in world coordinates
        vec3 UP;        // Camera up vector
        vec3 X;         // Camera X axis
        vec3 Y;         // Camera Y axis
        vec3 Z;         // Camera Z axis

        //// Rays 3D

        vec3 origin;   // Origin of the camera ray
        vec3 target;   // Target of the camera ray
        vec3 ray;      // Camera ray normalized vector
        float orbital; // Displacement of origin and target from the position
        float dolly;   // Displacement of the origin from the position

        //// Rays 2D

        vec3 plane_point;
        vec3 plane_normal;
        vec2 screen;
        vec2 gluv;
        vec2 agluv;
        vec2 stuv;
        vec2 astuv;
        vec2 glxy;
        vec2 stxy;
        bool out_of_bounds;

        //// Virtual Reality
        float separation;

        //// Parameters
        float isometric;
        float zoom;
    };

    /* Builds a rectangle where the camera is looking at centered on the origin */
    vec3 CameraRectangle(Camera camera, float size) {
        return size*(camera.screen.x*camera.X + camera.screen.y*camera.Y);
    }

    vec3 CameraRayOrigin(Camera camera) {
        return camera.position
            + CameraRectangle(camera, camera.zoom*camera.isometric)
            - (camera.Z*camera.orbital)
            - (camera.Z*camera.dolly);
    }

    vec3 CameraRayTarget(Camera camera) {
        return camera.position
            + CameraRectangle(camera, camera.zoom)
            - (camera.Z*camera.orbital)
            + camera.Z;
    }

    Camera CameraRay2D(Camera camera) {

        // Calculate the interstion with the plane define by a point and norm
        // Note: (t < 0) the intersection is behind the camera
        // https://en.wikipedia.org/wiki/Line%E2%80%93plane_intersection
        float num = dot(camera.plane_point - camera.origin, camera.plane_normal);
        float den = dot(camera.ray, camera.plane_normal);
        float t = num/den;

        // Calculate the intersection point
        camera.gluv  = (camera.origin + (t*camera.ray)).xy;
        camera.stuv  = gluv2stuv(camera.gluv);
        camera.agluv = vec2(camera.gluv.x/iAspectRatio, camera.gluv.y);
        camera.astuv = gluv2stuv(camera.agluv);
        camera.stxy  = (iResolution * camera.astuv);
        camera.glxy  = (camera.stxy - iResolution/2.0);
        camera.out_of_bounds = (t < 0) || (abs(gluv.x) > iWantAspect);
        return camera;
    }

    Camera iCameraProject(Camera camera) {

        // Perspective - Simple origin and target
        if (camera.projection == CameraProjectionPerspective) {
            camera.origin = CameraRayOrigin(camera);
            camera.target = CameraRayTarget(camera);

        // Virtual Reality - Emulate two cameras, same as perspective
        } else if (camera.projection == CameraProjectionVirtualReality) {

            // Make both sides of the uv a new GLUV
            int side = (agluv.x <= 0 ? 1 : -1);
            camera.screen += side*vec2(iAspectRatio/2, 0);

            // Get the VR Horizontal Separation and add to the new own projections
            vec3 separation = camera.X * side*(camera.separation/2.0);
            camera.origin = CameraRayOrigin(camera) - separation;
            camera.target = CameraRayTarget(camera) - separation;

        // Equirectangular
        } else if (camera.projection == CameraProjectionEquirectangular) {
            camera.origin = camera.position;

            float phi   = (1/camera.zoom) * (PI*camera.screen.y/2);
            float theta = (1/camera.zoom) * (PI*camera.screen.x/iAspectRatio);
            vec3 target = camera.Z;

            target = rotate3d(target, camera.X, -phi);
            target = rotate3d(target, camera.Y, theta);

            camera.target = camera.position + target;
        }

        // Origin and target rays projections
        camera.ray = normalize(camera.target - camera.origin);

        return CameraRay2D(camera);
    }

#endif

// Initialization

Camera iCamera;

void iCameraInit() {
    iCamera.plane_point   = vec3(0, 0, 1);
    iCamera.plane_normal  = vec3(0, 0, 1);
    iCamera.screen        = gluv;
    iCamera.mode          = iCameraMode;
    iCamera.projection    = iCameraProjection;
    iCamera.position      = iCameraPosition;
    iCamera.orbital       = iCameraOrbital;
    iCamera.dolly         = iCameraDolly;
    iCamera.UP            = iCameraUP;
    iCamera.X             = iCameraX;
    iCamera.Y             = iCameraY;
    iCamera.Z             = iCameraZ;
    iCamera.isometric     = iCameraIsometric;
    iCamera.zoom          = iCameraZoom;
    iCamera.separation    = iCameraVRSeparation;
    iCamera.out_of_bounds = false;
    iCamera = iCameraProject(iCamera);
}

