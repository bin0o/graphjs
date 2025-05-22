const helper = require('./helper');
const f = function () {
    const v5 = helper.g();
    v5;
};
const v6 = {};
v6.f = f;
module.exports = v6;