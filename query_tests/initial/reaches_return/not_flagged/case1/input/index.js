const helper = require('./helper')

function ola(input){
    const coco = 7;
    return eval(helper.g(input, coco))
}

module.exports={ola};