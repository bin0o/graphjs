function g(userInput) {
  data.input = userInput;
  return data;
}

function f(x) {
  eval(g(x))
}

module.exports = {f}
