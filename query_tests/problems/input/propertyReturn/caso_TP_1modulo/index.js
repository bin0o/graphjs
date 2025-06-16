
function g(userInput) {
  return userInput
}

function f(x) {
  eval(g(x))
}

module.exports = {f}
