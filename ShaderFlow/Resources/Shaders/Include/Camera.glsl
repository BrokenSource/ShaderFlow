#ifndef SHADERFLOW_CAMERA
#define SHADERFLOW_CAMERA

    // ShaderFlowCamera Mode Enum
    #define ShaderFlowCameraModeFreeCamera 1
    #define ShaderFlowCameraMode2D 2
    #define ShaderFlowCameraModeSpherical 3

    // ShaderFlowCamera Projection Enum
    #define ShaderFlowCameraProjectionPerspective 0
    #define ShaderFlowCameraProjectionVirtualReality 1
    #define ShaderFlowCameraProjectionEquirectangular 2

    struct ShaderFlowCamera {

        //// Basic

        int  mode;        // ShaderFlowCamera mode, defined on by the ShaderFlowCameraMode enum
        int  projection;  // ShaderFlowCamera projection, defined on by the ShaderFlowCameraProjection enum

        //// Position

        vec3 position;  // ShaderFlowCamera position in world coordinates
        vec3 UP;        // ShaderFlowCamera up vector
        vec3 X;         // ShaderFlowCamera X axis
        vec3 Y;         // ShaderFlowCamera Y axis
        vec3 Z;         // ShaderFlowCamera Z axis

        //// Rays 3D

        vec3 origin;   // Origin of the camera ray
        vec3 target;   // Target of the camera ray
        vec3 ray;      // ShaderFlowCamera ray normalized vector
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
    vec3 ShaderFlowCameraRectangle(ShaderFlowCamera camera, float size) {
        return size*(camera.screen.x*camera.X + camera.screen.y*camera.Y);
    }

    vec3 ShaderFlowCameraRayOrigin(ShaderFlowCamera camera) {
        return camera.position
            + ShaderFlowCameraRectangle(camera, (1/camera.zoom)*camera.isometric)
            - (camera.Z*camera.orbital)
            - (camera.Z*camera.dolly);
    }

    vec3 ShaderFlowCameraRayTarget(ShaderFlowCamera camera) {
        return camera.position
            + ShaderFlowCameraRectangle(camera, (1/camera.zoom))
            - (camera.Z*camera.orbital)
            + camera.Z;
    }

    ShaderFlowCamera ShaderFlowCameraRay2D(ShaderFlowCamera camera) {

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

    ShaderFlowCamera iProjectShaderFlowCamera(ShaderFlowCamera camera) {

        // Perspective - Simple origin and target
        if (camera.projection == ShaderFlowCameraProjectionPerspective) {
            camera.origin = ShaderFlowCameraRayOrigin(camera);
            camera.target = ShaderFlowCameraRayTarget(camera);

        // Virtual Reality - Emulate two cameras, same as perspective
        } else if (camera.projection == ShaderFlowCameraProjectionVirtualReality) {

            // Make both sides of the uv a new GLUV
            int side = (agluv.x <= 0 ? 1 : -1);
            camera.screen += side*vec2(iAspectRatio/2, 0);

            // Get the VR Horizontal Separation and add to the new own projections
            vec3 separation = camera.X * side*(camera.separation/2.0);
            camera.origin = ShaderFlowCameraRayOrigin(camera) - separation;
            camera.target = ShaderFlowCameraRayTarget(camera) - separation;

        // Equirectangular
        } else if (camera.projection == ShaderFlowCameraProjectionEquirectangular) {
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

        return ShaderFlowCameraRay2D(camera);
    }

#endif

// Initialization

ShaderFlowCamera iInitShaderFlowCamera(vec2 gluv) {
    ShaderFlowCamera camera;
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

ShaderFlowCamera iCamera = iProjectShaderFlowCamera(iInitShaderFlowCamera(gluv));

