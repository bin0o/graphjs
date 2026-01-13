const sink = require("./axiosSink");

function f(x){
    eval(sink.httpAdapter(x));
}