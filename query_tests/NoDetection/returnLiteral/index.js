function g(userInput) {
  return 5;
}

function f(x) {
  eval(g(x))
}

module.exports = {f}
