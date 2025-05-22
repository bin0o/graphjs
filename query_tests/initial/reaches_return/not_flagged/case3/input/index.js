// index.js
const helper = require('./helper');

function wrapper(x) {
  return helper.dangerous(x); // ARG edge from x to CALL -> dangerous
}

eval(wrapper(userInput));
