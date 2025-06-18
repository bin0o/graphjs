function g(userInput,noThreat) {
  return noThreat;
}

function f(x) {
  eval(g(x,5))
}

module.exports = {f}
