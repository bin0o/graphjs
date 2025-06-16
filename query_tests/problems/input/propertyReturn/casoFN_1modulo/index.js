
function g(userInput) {
  return { data: userInput };
}

function f(x) {
  eval(g(x).data)
}

module.exports = {f}
