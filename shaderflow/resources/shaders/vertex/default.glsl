void main() {

    // Fullscreen Rectangle
    gl_Position = vec4(vertex_position, 0.0, 1.0);
    instance = gl_InstanceID;

    // // Coordinates Recap:
    // ST = 'ShaderToy', (0, 0) to (1, 1), center half
    // GL = 'OpenGL', (-1, -1) to (1, 1), center zero

    // Continuous coordinates
    agluv = vertex_gluv;
    gluv  = agluv2gluv(agluv);
    astuv = gluv2stuv(agluv);
    stuv  = gluv2stuv(gluv);

    // Pixel coordinates
    stxy = (iResolution*astuv) + 1;
    glxy = (stxy - iResolution/2);
    fragCoord = stxy;
}
