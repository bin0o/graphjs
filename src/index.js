// unsafe param used as sink arg

const helper = require('./helper');

function f(x_f,y_f) {
    helper.g(x_f,y_f);
}

module.exports = {f}