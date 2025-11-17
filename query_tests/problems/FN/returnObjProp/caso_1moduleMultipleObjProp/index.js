function g(userInput) {
  const data = {input1: {input2: userInput}}
  return data;
}

function f(x) {
  eval(g(x).input1.input2);
}

module.exports = {f}
