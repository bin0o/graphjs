// no graphjs original este case é detetado por puro acaso:
    // - FP/returnParamNotExported adiciona um tainted edge porque o helper.g é uma exported function call e é flagged como undefined
    // - por causa disto ele deteta este caso quando acontece em diff files

const helper = require('./helper')

function f(x) {
    eval(helper.g(x).data)
}

module.exports = {f}