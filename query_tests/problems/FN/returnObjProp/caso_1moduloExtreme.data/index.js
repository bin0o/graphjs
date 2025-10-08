function g(userInput) {
  const data = {};
  data.input1 = userInput;
  return data;
}

function f(x) {
  eval(g(x).input1)
}

module.exports = {f}
