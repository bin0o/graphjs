// //deteta
// function f(x) {
//     const ola = {x, y: "adeus"};

//     eval(ola.x)
// }

// //deteta

// function f(x) {
//     const ola = {x};

//     eval(ola.x)
// }

// não deteta

function f(x) {
    const ola = {x:x,adeus: 5};

    eval(ola.adeus)
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