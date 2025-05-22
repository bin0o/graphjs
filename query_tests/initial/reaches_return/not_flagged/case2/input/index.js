const helper = require('./helper')

function ola(input){
    return eval(helper.g(input, 7))
}

module.exports={ola};