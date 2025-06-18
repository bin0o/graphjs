const helper = require('./helper')

function f(x) {
  eval(helper.g(x,5))
}

module.exports = {f}
