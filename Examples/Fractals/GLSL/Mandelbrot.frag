
// vec2 complex_xy2rt(vec2 a) {
//     return vec2(
//         sqrt(a.x*a.x + a.y*a.y),
//         atan(a.y, a.x)
//     );
// }

// vec2 complex_rt2xy(vec2 a) {
//     return vec2(a.x*cos(a.y), a.x*sin(a.y));
// }

// vec2 complex_mul_rt(vec2 a, vec2 b) {
//     return vec2((a.x * b.x), (a.y + b.y));
// }

// vec2 complex_div_rt(vec2 a, vec2 b) {
//     return vec2((a.x / b.x), (a.y - b.y));
// }

// vec2 complex_add_xy(vec2 a, vec2 b) {
//     return vec2(a.x + b.x, a.y + b.y);
// }

// vec2 complex_add_rt(vec2 a, vec2 b) {
//     return complex_xy2rt(complex_add_xy(
//         complex_rt2xy(a),
//         complex_rt2xy(b)
//     ));
// }

// vec2 complex_sub_xy(vec2 a, vec2 b) {
//     return vec2(a.x - b.x, a.y - b.y);
// }


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
    iCameraInit();

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