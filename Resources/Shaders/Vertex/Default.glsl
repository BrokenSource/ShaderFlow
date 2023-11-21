void main() {
    gl_Position = vec4(vertex_position, 0.0, 1.0);
    gluv = vertex_gluv;
    stuv = (gluv*0.5) + 0.5;
    instance = gl_InstanceID;
}
