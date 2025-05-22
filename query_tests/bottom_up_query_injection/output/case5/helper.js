const processWithEval = function (input) {
    const v1 = eval(input);
    v1;
};
const v2 = {};
v2.processWithEval = processWithEval;
module.exports = v2;