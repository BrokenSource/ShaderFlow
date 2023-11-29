void main() {
    // Export vertex position and instance
    gl_Position = vec4(vertex_position, 0.0, 1.0);
    instance = gl_InstanceID;

    // Get and fix GLUV by aspect ratio
    gluv = vertex_gluv;
    gluv.x *= iAspectRatio;

    // Get STUV from fixed GLUV
    stuv = gluv2stuv(gluv);

    // Export absolute coordinates
    agluv = vertex_gluv;
    astuv = gluv2stuv(agluv);
}
