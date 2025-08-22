function g(userInput) {
  data.input = userInput;
  return data;
}

function f(x) {
  eval(g(x).input)
}

module.exports = {f}
