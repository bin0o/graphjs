const helper = require('./helper')

function f(){
    eval(helper.g("5"))
}

module.exports = {f}