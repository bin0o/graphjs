function g(userInput) {
  data.input.input = userInput;
  return data;
}

function f(x) {
  eval(g(x))
}

module.exports = {f}
