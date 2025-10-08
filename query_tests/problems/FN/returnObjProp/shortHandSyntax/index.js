function f(userInput) {
    let path = userInput
    const result = {path: path, method: 25, prop: 'userInput'}
    eval(result.path)
}

module.exports = {f}