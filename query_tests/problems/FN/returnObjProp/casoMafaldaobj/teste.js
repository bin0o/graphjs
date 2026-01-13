// //deteta
// function f(x) {
//     const ola = {x: x};

//     eval(ola.x)
// }

// //deteta

// function f(x) {
//     const ola = {x};

//     eval(ola.x)
// }

// não deteta

// function f(x) {
//     const ola = {x: x,adeus};

//     eval(ola.x)
// }

// não deteta

function f(x) {
    const ola = {x,adeus};

    eval(ola.x)
}

// //não deteta

// function f(x) {
//     const ola = {x: x};

//     eval(ola)
// }

// não deteta

// function f(x) {
//     const ola = {x:x, adeus};

//     eval(ola.x)
// }