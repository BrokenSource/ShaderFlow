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

    /* Build a projection plane at the origin where the camera is looking */
    vec3 CameraRectangle(Camera camera, vec2 gluv, float size) {
        return size*(gluv.x*camera.X + gluv.y*camera.Y);
    }

    vec3 CameraRayOrigin(Camera camera, vec2 gluv) {
        return camera.position
            + CameraRectangle(camera, gluv, camera.zoom*camera.isometric)
            - (camera.Z*camera.orbital)
            - (camera.Z*camera.dolly);
    }

    vec3 CameraRayTarget(Camera camera, vec2 gluv) {
        return camera.position
            + CameraRectangle(camera, gluv, camera.zoom)
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
        camera.agluv = (camera.gluv / vec2(iAspectRatio, 1));
        camera.stuv  = (camera.gluv  + 1.0)/2.0;
        camera.astuv = (camera.agluv + 1.0)/2.0;
        camera.stxy  = (iResolution * camera.astuv);
        camera.glxy  = (camera.stxy - iResolution/2.0);
        camera.out_of_bounds = (t < 0) || (abs(gluv.x) > iWantAspect);
        return camera;
    }

    Camera CameraProject(Camera camera) {

        // Perspective - Simple origin and target
        if (camera.projection == CameraProjectionPerspective) {
            camera.origin = CameraRayOrigin(camera, gluv);
            camera.target = CameraRayTarget(camera, gluv);

        // Virtual Reality - Emulate two cameras, same as perspective
        } else if (camera.projection == CameraProjectionVirtualReality) {

            // Each side of the screen has its own gluv at the center
            vec2 gluv = gluv - sign(agluv.x) * vec2(iAspectRatio/2.0, 0.0);

            // The eyes are two cameras displaced by the separation
            camera.position += (sign(agluv.x) * camera.separation) * camera.X;
            camera.origin = CameraRayOrigin(camera, gluv);
            camera.target = CameraRayTarget(camera, gluv);

        // Equirectangular
        } else if (camera.projection == CameraProjectionEquirectangular) {

            // Map a sphere to the screen,
            float inclination = (camera.zoom) * (PI*agluv.y/2);
            float azimuth     = (camera.zoom) * (PI*agluv.x/1);

            // Rotate the forward vector
            vec3 target = camera.Z;
            target = rotate3d(target, camera.X, -inclination);
            target = rotate3d(target, camera.Y, +azimuth);

            // All rays originate from the position
            camera.origin = camera.position;
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
    iCamera = CameraProject(iCamera);
}
