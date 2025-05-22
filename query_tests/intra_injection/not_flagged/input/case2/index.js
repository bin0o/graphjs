const helper = require('./helper')

function f(x){
    eval(helper.g(x))
}

module.exports={f};