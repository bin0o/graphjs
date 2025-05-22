const helper = require('./helper');
const ola = function (input) {
    const coco = 7;
    const v5 = helper.g(input, coco);
    const v6 = eval(v5);
    return v6;
};
const v7 = {};
v7.ola = ola;
module.exports = v7;