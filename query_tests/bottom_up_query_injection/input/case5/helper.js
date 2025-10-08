// helper.js
function internalFunction(param) {
    // This param is not automatically marked as exported
    return param;
  }
  
  function processWithEval(input) {
    const result = internalFunction(input);
    eval(result); // sink
  }
  
  module.exports = { processWithEval };