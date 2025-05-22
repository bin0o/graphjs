const index = require('./index')

function wrapper(x){
    index.f(x)
}

module.exports = {wrapper}