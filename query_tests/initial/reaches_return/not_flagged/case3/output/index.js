const helper = require('./helper');
const wrapper = function (x) {
    const v5 = helper.dangerous(x);
    return v5;
};
const v6 = wrapper(userInput);
const v7 = eval(v6);
v7;