// index.js
const helper = require('./helper');

function handler(userInput) {
  const validated = helper.validateInput(userInput);
  helper.execCode(validated); // calls sink with tainted input
}

function anotherHandler(userInput) {
  handler(userInput); // reuses the same parameter name
}

module.exports = { handler, anotherHandler };