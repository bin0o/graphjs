function f(x) {
    switch(y) {
        case 1:
            _req = require('./default1');
        case 2:
            _req = require('./adeus');
        default:
            _req = require('./ola');
    }
    _req(x)
}