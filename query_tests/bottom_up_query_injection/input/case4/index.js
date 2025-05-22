// index.js
const helper = require('./helper');

function commonUtility(data) {
  return data; // this parameter will be checked twice
}

function handler(userInput) {
  const result1 = commonUtility(userInput);
  const result2 = commonUtility(result1); // creates second path to same parameter
  helper.processWithEval(result2);
}

module.exports = { handler };