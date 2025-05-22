// helper.js
function processData(input) {
    return input;
  }
  
  function validateInput(data) {
    return processData(data);
  }
  
  function execCode(code) {
    eval(code); // sink
  }
  
  module.exports = { validateInput, execCode };