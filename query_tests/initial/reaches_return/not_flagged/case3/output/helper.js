const dangerous = function (input) {
    return input;
};
const v1 = {};
v1.dangerous = dangerous;
module.exports = v1;