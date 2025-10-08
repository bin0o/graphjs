function g(input){
    const ola = {input}
    return ola
}

function f(userInput) {
    let path = g(userInput)
    const result = {path, method: 25, prop: 'userInput'}
    eval(result)
}

module.exports = {f}
