const f = function () {
    const v3 = eval('5');
    v3;
};
const v4 = {};
v4.f = f;
module.exports = v4;