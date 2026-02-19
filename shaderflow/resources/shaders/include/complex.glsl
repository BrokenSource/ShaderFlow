/* A complex number can be represented by a vec2 */

// Addition
vec2 cadd(vec2 a, vec2 b) {
    return a + b;
}

// Subtraction
vec2 csub(vec2 a, vec2 b) {
    return a - b;
}

// Magnitude
float cmag(vec2 a) {
    return length(a);
}

// Cartesian to Polar
vec2 cpol(vec2 a) {
    return vec2(
        length(a),
        atan(a.y, a.x)
    );
}

// Polar to Cartesian
vec2 ccar(vec2 polar) {
    return vec2(
        polar.x * cos(polar.y),
        polar.x * sin(polar.y)
    );
}

// Multiplication
vec2 cmul(vec2 a, vec2 b) {
    return vec2(
        (a.x * b.x) - (a.y * b.y),
        (a.x * b.y) + (a.y * b.x)
    );
}

// Division
vec2 cdiv(vec2 a, vec2 b) {
    float den = (b.x * b.x) + (b.y * b.y);
    return vec2(
        ((a.x * b.x) + (a.y * b.y)) / den,
        ((a.y * b.x) - (a.x * b.y)) / den
    );
}

// Conjugate
vec2 cconj(vec2 a) {
    return vec2(a.x, -a.y);
}

// Exponential
vec2 cexp(vec2 a) {
    float expx = exp(a.x);
    return vec2(
        expx * cos(a.y),
        expx * sin(a.y)
    );
}
