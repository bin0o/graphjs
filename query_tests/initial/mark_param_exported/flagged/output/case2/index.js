const helper = require('./helper');
const f = function () {
    const v5 = helper.g('5');
    const v6 = eval(v5);
    v6;
};
const v7 = {};
v7.f = f;
module.exports = v7;