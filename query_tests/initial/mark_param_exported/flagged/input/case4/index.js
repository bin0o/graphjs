function processUserInput(input) {
    return sanitize(input);
}

function executeQuery(query) {
    db.query(query); // SINK
}

function handleRequest(req) {
    const userInput = req.params.input; // SOURCE
    const processedInput = processUserInput(userInput);
    executeQuery(processedInput);
}
  

module.exports = {handleRequest}