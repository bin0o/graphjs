function f(userInput) {
    let result = {data: userInput}
    eval(result.data)
}

module.exports = {f}
