const v2 = function f(x) {
    const v1 = eval(x);
    v1;
};
let v = {};
v.f = v2;
let z = {};
z.a = v;
const v3 = {};
v3.z = z;
module.exports = v3;