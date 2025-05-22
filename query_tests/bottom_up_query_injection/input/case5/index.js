// index.js
const helper = require('./helper');

function handler(userInput) {
  helper.processWithEval(userInput);
}

module.exports = { handler };