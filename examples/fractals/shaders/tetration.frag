
// Todo: Port to a common library
struct ComplexNumber {
    float x, y; // Rectangular
    float r, t; // Polar
};

ComplexNumber UpdatePolar(ComplexNumber z) {
   z.r = sqrt(z.x*z.x + z.y*z.y);
   z.t = atan(z.y, z.x);
   return z;
}

ComplexNumber UpdateCartesian(ComplexNumber z) {
   z.x = z.r * cos(z.t);
   z.y = z.r * sin(z.t);
   return z;
}

// Complex number power magic shenganigans
ComplexNumber ComplexNumberPower(ComplexNumber a, ComplexNumber b) {
   ComplexNumber z;
   z.r = pow(a.r, b.x) * exp(-b.y * a.t);
   z.t = b.y * log(a.r) + (b.x * a.t);
   return UpdateCartesian(z);
}

void main() {
    GetCamera(iCamera);
    vec2 gluv = iCamera.gluv;

    // Get complex from screen
    ComplexNumber C;
    C.x = gluv.x;
    C.y = gluv.y;
    C = UpdatePolar(C);
    ComplexNumber Z = C;

    // Core fractal loop
    int MAX_STEPS = 67;
    int it = 0;

    for (it=0; it<MAX_STEPS; it++) {
        Z = ComplexNumberPower(C, Z);
        if (Z.r > 100.0)
            break;
    }

    // Final color something
    float k = it / MAX_STEPS;
    float theta = atan2n(Z.y, Z.x);
    vec3 col = hsv2rgb(theta, 1.0, k);

    fragColor = vec4(col, 1.0);
}