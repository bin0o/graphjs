const helper = require('./helper');
const commonUtility = function (data) {
    return data;
};
const handler = function (userInput) {
    const result1 = commonUtility(userInput);
    const result2 = commonUtility(result1);
    const v5 = helper.processWithEval(result2);
    v5;
};
const v6 = {};
v6.handler = handler;
module.exports = v6;