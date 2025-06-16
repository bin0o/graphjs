const helper = require('./helper')

function f(x) {
    eval(helper.g(x).data)
}

module.exports = {f}