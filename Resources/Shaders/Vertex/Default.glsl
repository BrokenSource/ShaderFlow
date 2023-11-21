void main() {
    gl_Position = vec4(vertex_position, 0.0, 1.0);
    gluv = vertex_uv;
    instance = gl_InstanceID;
}
