const helper = require('./helper');
const handler = function (userInput) {
    const validated = helper.validateInput(userInput);
    const v7 = helper.execCode(validated);
    v7;
};
const anotherHandler = function (userInput) {
    const v8 = handler(userInput);
    v8;
};
const v9 = {};
v9.handler = handler;
v9.anotherHandler = anotherHandler;
module.exports = v9;