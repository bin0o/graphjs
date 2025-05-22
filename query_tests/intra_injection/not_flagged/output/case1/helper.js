const g = function (x) {
    const v1 = eval(x);
    v1;
};
const v2 = {};
v2.g = g;
module.exports = v2;