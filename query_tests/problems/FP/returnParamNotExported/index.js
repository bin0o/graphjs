// this is a FP because helper.g returns 0 and not the tainted param

const helper = require('./helper')

function f(x){
    eval(helper.g(x))
}

module.exports={f};