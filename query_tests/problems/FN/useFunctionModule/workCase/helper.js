// this case is detected because function g only acts as a middleman for the tainted param
// it only makes a difference when we have to analyse the inside of the exported function
// because the parser does not recognize the function g as g but as helper.g
// this works because the propagation query is independent of the above error
function g(x){
    return x
}

module.exports = g