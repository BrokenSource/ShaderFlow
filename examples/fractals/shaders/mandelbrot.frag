struct Complex {
    float x;
    float y;
    float r;
    float t;
};

// Updating

Complex complex_update_rt(Complex a) {
    a.r = sqrt(a.x*a.x + a.y*a.y);
    a.t = atan(a.y, a.x);
    return a;
}

Complex complex_update_xy(Complex a) {
    a.x = a.r*cos(a.t);
    a.y = a.r*sin(a.t);
    return a;
}

// Initialization

Complex complex_xy(vec2 z) {
    return complex_update_rt(
        Complex(z.x, z.y, 0, 0));
}

Complex complex_xy(float x, float y) {
    return complex_xy(vec2(x, y));
}

Complex complex_rt(vec2 z) {
    return complex_update_xy(
        Complex(0, 0, z.x, z.y));
}

Complex complex_rt(float r, float t) {
    return complex_rt(vec2(r, t));
}

// Operations

Complex complex_add(Complex a, Complex b) {
    return complex_update_rt(Complex(
        (a.x + b.x), (a.y + b.y), 0, 0
    ));
}

Complex complex_sub(Complex a, Complex b) {
    return complex_update_rt(Complex(
        (a.x - b.x), (a.y - b.y), 0, 0
    ));
}

Complex complex_mul(Complex a, Complex b) {
    return complex_update_xy(Complex(
        0, 0, (a.r * b.r), (a.t + b.t)
    ));
}

Complex complex_div(Complex a, Complex b) {
    return complex_update_xy(Complex(
        0, 0, (a.r / b.r), (a.t - b.t)
    ));
}

Complex complex_burning_ship(Complex a) {
    Complex z = complex_update_rt(Complex(abs(a.x), abs(a.y), 0, 0));
    return complex_update_rt(complex_mul(z, z));
}

void main() {
    GetCamera(iCamera);

    if (iCamera.out_of_bounds) {
        fragColor = vec4(palette_magma(0), 1);
        return;
    }

    Complex z = complex_xy(iCamera.gluv - vec2(0.5, 0));
    Complex c = z;

    float quality = 1000*iQuality;
    float iter = 0;

    for (; iter<quality; iter++) {
        if (z.r > 2.0) break;
        z = complex_add(complex_mul(z, z), c);
    }

    // Nice shading pallete
    float t = pow(1 - iter / quality, 20);
    fragColor = vec4(palette_magma(t), 1);
}