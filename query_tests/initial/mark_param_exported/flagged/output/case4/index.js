const processUserInput = function (input) {
    const v6 = sanitize(input);
    return v6;
};
const executeQuery = function (query) {
    const v7 = db.query(query);
    v7;
};
const handleRequest = function (req) {
    const v8 = req.params;
    const userInput = v8.input;
    const processedInput = processUserInput(userInput);
    const v9 = executeQuery(processedInput);
    v9;
};
const v10 = {};
v10.handleRequest = handleRequest;
module.exports = v10;